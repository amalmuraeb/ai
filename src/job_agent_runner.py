"""
Phases 3-6 - Job-Agent Runner
Coordinates shared execution, validation, reporting, and publication.
"""

import json
import shutil
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from time import perf_counter

from src.application_history import ApplicationHistory
from src.document_manager import DocumentManager
from src.job_analysis_agent import JobAnalysisAgent
from src.job_pipeline import (
    JobPipeline,
    format_elapsed_time,
    parse_elapsed_time,
)
from src.job_provisioner import JobProvisioner
from src.version import __version__


REPORT_CATEGORIES = (
    "apply",
    "review",
    "do_not_apply",
    "skipped",
    "unreachable",
)


class JobAgentRunner(ABC):
    """Run one job-board source through the shared Phase 3–5 workflow."""

    def __init__(self, user_profile, remote=False):
        self.user_profile = user_profile
        self.remote = remote

    @abstractmethod
    def create_source(self):
        """Return the job-board source used for this run."""

    def create_provisioner(self) -> JobProvisioner:
        """Return the provisioner, allowing deterministic test doubles."""

        return JobProvisioner(self.user_profile)

    def create_agent(self) -> JobAnalysisAgent:
        """Return the analysis agent, allowing deterministic test doubles."""

        return JobAnalysisAgent(self.user_profile)

    def analysis_service_name(self) -> str:
        """Return the analysis backend name used in progress output."""

        return "Ollama"

    def create_document_manager(self) -> DocumentManager:
        """Return the common Phase 6 planner and report writer."""
        return DocumentManager()

    def load_document_postings(self, apply_jobs):
        """Retrieve posting bodies for Phase 6 in a board-specific runner."""
        raise NotImplementedError

    @staticmethod
    def print_completion(
        step_name: str,
        message: str,
        elapsed_seconds: float,
    ) -> None:
        """Print a consistent phase or major-step completion message."""

        print("\n" + "=" * 60)
        print(f"{step_name} complete.")
        print(message)
        print(f"Elapsed time: {format_elapsed_time(elapsed_seconds)}.")
        print("=" * 60)

    @staticmethod
    def _report_files(
        report_paths: dict[str, Path],
    ) -> dict[str, Path]:
        return {
            category: report_paths[category]
            for category in REPORT_CATEGORIES
        }

    def _stamp_scope(self, report):
        """Record the independently published job channel in metadata."""
        metadata = report.setdefault("report_metadata", {})
        metadata["software_version"] = __version__
        metadata["job_scope"] = (
            "remote" if self.remote else "non_remote"
        )
        return report

    @staticmethod
    def _load_optional_report(path: Path) -> dict:
        if not path.is_file():
            return {"jobs": []}
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _report_urls(report: dict) -> set[str]:
        """Return source URLs from flat or nested private-history records."""
        urls = set()
        for item in report.get("jobs", []):
            if not isinstance(item, dict):
                continue
            job = item.get("job", item)
            if isinstance(job, dict) and job.get("source_url"):
                urls.add(job["source_url"])
        return urls

    def _private_suppression_urls(self, published_paths):
        """Load applied and manually closed URLs before recommendation work."""
        archived_applied_urls = self._report_urls(
            self._load_optional_report(published_paths["applied"])
        )
        document_report = self._load_optional_report(
            published_paths["document_manager"]
        )
        other_document_path = published_paths.get("other_document_manager")
        other_document_report = (
            self._load_optional_report(other_document_path)
            if other_document_path is not None
            else {"jobs": []}
        )
        pending_applied_urls = {
            item.get("job", {}).get("source_url")
            for item in (
                document_report.get("jobs", [])
                + other_document_report.get("jobs", [])
            )
            if isinstance(item, dict)
            and isinstance(item.get("job"), dict)
            and item["job"].get("applied?") == "Yes"
            and item["job"].get("source_url")
        }
        closed_path = published_paths.get("closed")
        closed_urls = (
            self._report_urls(self._load_optional_report(closed_path))
            if closed_path is not None
            else set()
        )
        return archived_applied_urls | pending_applied_urls, closed_urls

    def _reconcile_application_history(
        self,
        *,
        pipeline,
        pipeline_result,
        category_reports,
        write_paths,
        published_paths,
        job_board,
        pipeline_name,
        privately_suppressed_urls=None,
        pre_suppressed_applied_count=0,
        pre_suppressed_closed_count=0,
    ):
        """Merge fresh apply results with durable manual application state."""
        history = ApplicationHistory().reconcile(
            category_reports["apply"]["jobs"],
            deterministically_excluded_urls={
                job.get("source_url")
                for job in pipeline_result["jobs"]
                if job.get("skipped_before_llm") is True
                and job.get("source_url")
            },
            # Closed records are removed permanently. Applied records marked
            # in Document Manager must remain visible to reconciliation long
            # enough to be copied into the private applied archive.
            privately_suppressed_urls=privately_suppressed_urls,
            previous_apply_report=self._load_optional_report(
                published_paths["apply"]
            ),
            previous_document_report=self._load_optional_report(
                published_paths["document_manager"]
            ),
            previous_applied_report=self._load_optional_report(
                published_paths["applied"]
            ),
            job_board=job_board,
            pipeline_name=pipeline_name,
            remote=self.remote,
        )

        applied_urls = history["applied_urls"]
        retained_urls = history["retained_urls"]
        historical_urls = applied_urls | retained_urls
        prior_analyzed_count = pipeline_result["run_summary"].get(
            "fresh_analyzed_count",
            sum(
                category_reports[name]["job_count"]
                for name in ("apply", "review", "do_not_apply")
            ),
        )
        for job in pipeline_result["jobs"]:
            if job.get("source_url") in applied_urls:
                # This in-memory value explains why an otherwise matching
                # job is suppressed; applied duplicates are not published.
                job["final_recommendation"] = "skip"

        for category, report in category_reports.items():
            if category == "apply":
                jobs = history["apply_jobs"]
            else:
                jobs = [
                    job
                    for job in report["jobs"]
                    if job.get("source_url") not in historical_urls
                ]
            report["jobs"] = jobs
            report["job_count"] = len(jobs)
            pipeline.save_report(report, write_paths[category])

        pipeline.save_report(history["applied_report"], write_paths["applied"])
        current_reported = sum(
            report["job_count"] for report in category_reports.values()
        )
        current_analyzed = sum(
            category_reports[name]["job_count"]
            for name in ("apply", "review", "do_not_apply")
        )
        pipeline_result["run_summary"]["history_accounting_adjustment"] = (
            current_reported
            - pipeline_result["run_summary"]["jobs_discovered"]
        )
        pipeline_result["run_summary"]["suppressed_applied_duplicates"] = (
            pre_suppressed_applied_count
        )
        pipeline_result["run_summary"]["suppressed_closed_jobs"] = (
            pre_suppressed_closed_count
        )
        pipeline_result["run_summary"]["history_analyzed_adjustment"] = (
            current_analyzed - prior_analyzed_count
        )
        return history

    @staticmethod
    def _reset_directory(directory: Path) -> None:
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _publish_staged_reports(
        staging_dir: Path,
        live_dir: Path,
        staging_applied: Path | None = None,
        published_applied: Path | None = None,
    ) -> None:
        """Replace live reports and an optional external personal archive."""

        backup_dir = live_dir.with_name(f".{live_dir.name}_previous")
        applied_backup = None
        if backup_dir.exists():
            shutil.rmtree(backup_dir)

        external_applied = (
            staging_applied is not None
            and published_applied is not None
            and not staging_applied.is_relative_to(staging_dir)
        )
        if external_applied:
            published_applied.parent.mkdir(parents=True, exist_ok=True)
            applied_backup = published_applied.with_name(
                f".{published_applied.name}.previous"
            )
            if applied_backup.exists():
                applied_backup.unlink()
            if published_applied.exists():
                shutil.copy2(published_applied, applied_backup)

        had_live_reports = live_dir.exists()
        had_applied_report = bool(
            external_applied and published_applied.exists()
        )
        if had_live_reports:
            live_dir.replace(backup_dir)

        try:
            if external_applied:
                staging_applied.replace(published_applied)
            staging_dir.replace(live_dir)
        except Exception:
            if had_live_reports and backup_dir.exists():
                backup_dir.replace(live_dir)
            if external_applied:
                if had_applied_report and applied_backup.exists():
                    shutil.copy2(applied_backup, published_applied)
                elif not had_applied_report and published_applied.exists():
                    published_applied.unlink()
            raise
        else:
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
        finally:
            if applied_backup is not None and applied_backup.exists():
                applied_backup.unlink()
            if external_applied and staging_applied.exists():
                staging_applied.unlink()
            if staging_dir.exists():
                shutil.rmtree(staging_dir)

    @staticmethod
    def _update_summary_phase_timing(summary, phase_name, elapsed):
        """Replace one phase duration and adjust aggregate run time."""
        timing = summary.get("timing")
        if not isinstance(timing, dict):
            raise ValueError("Summary report has no timing object.")

        normalized_timing = {
            (name[:-4] if name.endswith("_sec") else name): value
            for name, value in timing.items()
        }
        phase_key = f"{phase_name}_elapsed_time"
        old_phase = parse_elapsed_time(
            normalized_timing.get(phase_key, "0 s")
        )
        old_total = parse_elapsed_time(
            normalized_timing["total_elapsed_time"]
        )
        normalized_timing[phase_key] = format_elapsed_time(elapsed)
        normalized_timing["total_elapsed_time"] = format_elapsed_time(
            max(0.0, old_total - old_phase + elapsed)
        )
        summary["timing"] = normalized_timing
        summary["report_metadata"]["report_version"] = "1.2"
        summary["report_metadata"]["software_version"] = __version__
        summary["report_metadata"]["report_created_at"] = (
            datetime.now().astimezone().isoformat(timespec="seconds")
        )
        return summary

    @staticmethod
    def _publish_staged_files(file_pairs):
        """Publish multiple files atomically using recoverable backups."""
        backups = []
        try:
            for staging_file, published_file in file_pairs:
                backup = published_file.with_name(
                    f".{published_file.name}.previous"
                )
                if backup.exists():
                    backup.unlink()
                existed = published_file.exists()
                if existed:
                    shutil.copy2(published_file, backup)
                backups.append((published_file, backup, existed))
                staging_file.replace(published_file)
        except BaseException:
            for published_file, backup, existed in backups:
                if existed and backup.exists():
                    shutil.copy2(backup, published_file)
                elif not existed and published_file.exists():
                    published_file.unlink()
            raise
        finally:
            for _, backup, _ in backups:
                if backup.exists():
                    backup.unlink()

    def run(
        self,
        *,
        write_paths: dict[str, Path],
        published_paths: dict[str, Path],
        pipeline_name: str,
        report_title: str,
        include_downstream: bool = True,
    ) -> dict:
        """Execute the shared workflow through Phase 5 or Phase 6."""

        run_started_at = datetime.now().astimezone()
        total_start = perf_counter()
        report_files = self._report_files(write_paths)
        published_report_files = self._report_files(published_paths)

        source = self.create_source()
        provisioner = self.create_provisioner()
        pipeline = JobPipeline(
            reader=source.reader,
            provisioner=provisioner,
            agent=self.create_agent(),
            user_profile=self.user_profile,
            debug_log_file=write_paths["log"],
        )

        phase_3_start = perf_counter()
        job_data_list = source.load_jobs()
        phase_3_elapsed = perf_counter() - phase_3_start

        if not job_data_list:
            raise RuntimeError(
                "Phase 3 returned no job records."
            )

        missing_urls = [
            index
            for index, job_data in enumerate(job_data_list, start=1)
            if not job_data.get("source_url")
        ]
        if missing_urls:
            raise RuntimeError(
                "Phase 3 did not preserve source_url for record(s): "
                + ", ".join(map(str, missing_urls))
            )

        job_board = job_data_list[0].get("source_type", "unknown")
        loaded_job_count = len(job_data_list)
        expected_remote = "Yes" if self.remote else "No"
        mismatched_scope = [
            job.get("source_url", f"record {index}")
            for index, job in enumerate(job_data_list, start=1)
            if job.get("remote?", "No") != expected_remote
        ]
        if mismatched_scope:
            raise RuntimeError(
                "The selected report scope does not match job metadata: "
                + ", ".join(mismatched_scope[:5])
            )
        applied_urls, closed_urls = self._private_suppression_urls(
            published_paths
        )
        applied_only_urls = applied_urls - closed_urls
        pre_suppressed_applied_count = sum(
            job.get("source_url") in applied_only_urls
            for job in job_data_list
        )
        pre_suppressed_closed_count = sum(
            job.get("source_url") in closed_urls
            for job in job_data_list
        )
        stale_urls = {
            job["source_url"]
            for job in job_data_list
            if provisioner.should_discard_stale_posting(job)
        }
        stale_only_urls = stale_urls - applied_urls - closed_urls
        discarded_stale_count = len(stale_only_urls)
        privately_suppressed_urls = applied_urls | closed_urls | stale_urls
        job_data_list = [
            job
            for job in job_data_list
            if job.get("source_url") not in privately_suppressed_urls
        ]

        pipeline.initialize_debug_report(
            total_jobs=len(job_data_list),
            job_board=job_board,
            run_started_at=run_started_at,
            report_title=report_title,
        )

        self.print_completion(
            step_name="PHASE 3 — Job Source Reader",
            message=(
                f"All {loaded_job_count} job posting(s) were "
                "successfully loaded into RAM.\n"
                f"{pre_suppressed_applied_count} already applied and "
                f"{pre_suppressed_closed_count} manually closed job(s) "
                "were excluded before Phase 4.\n"
                f"{discarded_stale_count} stale job posting(s) were "
                "discarded before Phase 4.\n"
                "Browser access is no longer required for this run."
            ),
            elapsed_seconds=phase_3_elapsed,
        )

        pipeline_result = pipeline.run(job_data_list)
        run_summary = pipeline_result["run_summary"]

        self.print_completion(
            step_name="PHASE 4 — Job Provisioner",
            message=(
                f"{run_summary['jobs_discovered']} job posting(s) "
                "were evaluated.\n"
                f"{run_summary['jobs_skipped_before_llm']} were "
                "skipped before LLM analysis.\n"
                f"{run_summary['jobs_sent_to_llm']} passed to Phase 5."
            ),
            elapsed_seconds=run_summary["phase_4_elapsed_time_sec"],
        )

        self.print_completion(
            step_name="PHASE 5 — Job Analysis Agent",
            message=(
                f"{run_summary['jobs_sent_to_llm']} job posting(s) "
                f"were sent to {self.analysis_service_name()}.\n"
                f"{run_summary['jobs_failed_llm']} analysis "
                "failure(s) were preserved for manual review."
            ),
            elapsed_seconds=run_summary["phase_5_elapsed_time_sec"],
        )

        report_start = perf_counter()
        category_reports = pipeline.save_partitioned_reports(
            pipeline_result=pipeline_result,
            report_files=report_files,
            job_board=job_board,
            run_started_at=run_started_at,
            pipeline_name=pipeline_name,
        )
        for report in category_reports.values():
            self._stamp_scope(report)
        pipeline_result["run_summary"]["fresh_analyzed_count"] = sum(
            category_reports[name]["job_count"]
            for name in ("apply", "review", "do_not_apply")
        )
        history = self._reconcile_application_history(
            pipeline=pipeline,
            pipeline_result=pipeline_result,
            category_reports=category_reports,
            write_paths=write_paths,
            published_paths=published_paths,
            job_board=job_board,
            pipeline_name=pipeline_name,
            privately_suppressed_urls=closed_urls | stale_urls,
            pre_suppressed_applied_count=pre_suppressed_applied_count,
            pre_suppressed_closed_count=pre_suppressed_closed_count,
        )
        pipeline_result["run_summary"]["discarded_stale_jobs"] = (
            discarded_stale_count
        )
        pipeline.save_apply_jobs_stats(
            history["apply_jobs"],
            write_paths["apply_stats"],
        )

        if not include_downstream:
            report_elapsed = perf_counter() - report_start
            total_elapsed = perf_counter() - total_start
            summary_report = pipeline.save_summary_report(
                pipeline_result=pipeline_result,
                category_reports=category_reports,
                output_file=write_paths["summary"],
                job_board=job_board,
                run_started_at=run_started_at,
                phase_3_elapsed_time_sec=phase_3_elapsed,
                report_writing_time_sec=report_elapsed,
                total_elapsed_time_sec=total_elapsed,
                report_files={
                    **published_report_files,
                    "apply_stats": published_paths["apply_stats"],
                    "document_manager": published_paths[
                        "document_manager"
                    ],
                    "applied": published_paths["applied"],
                    "summary": published_paths["summary"],
                    "log": published_paths["log"],
                },
                pipeline_name=pipeline_name,
            )
            self._stamp_scope(summary_report)
            pipeline.save_report(summary_report, write_paths["summary"])
            if not all(summary_report["validation"].values()):
                raise RuntimeError(
                    "RPA summary reconciliation failed: "
                    + json.dumps(
                        summary_report["validation"],
                        sort_keys=True,
                    )
                )
            return {
                "job_data_list": job_data_list,
                "pipeline_result": pipeline_result,
                "category_reports": category_reports,
                "application_history": history,
                "summary_report": summary_report,
                "report_paths": published_paths,
                "phase_3_elapsed_time_sec": phase_3_elapsed,
                "report_writing_time_sec": report_elapsed,
                "total_elapsed_time_sec": total_elapsed,
            }

        phase_6_start = perf_counter()
        apply_jobs = history["apply_jobs"]
        document_manager = self.create_document_manager()
        posting_results = self.load_document_postings(
            history["new_apply_jobs"]
        )
        application_plans = document_manager.build_application_plans(
            posting_results
        )
        application_plans = (
            history["retained_document_plans"] + application_plans
        )
        document_manager_report = (
            document_manager.save_document_manager_report(
                application_plans,
                write_paths["document_manager"],
                apply_jobs=apply_jobs,
                job_board=job_board,
                run_started_at=run_started_at,
                pipeline_name=pipeline_name,
            )
        )
        self._stamp_scope(document_manager_report)
        document_manager_report["report_metadata"][
            "last_job_sequence_number"
        ] = history["last_job_sequence_number"]
        write_paths["document_manager"].write_text(
            json.dumps(
                document_manager_report,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        phase_6_elapsed = perf_counter() - phase_6_start

        phase_6_validation = document_manager_report["validation"]
        if not all(phase_6_validation.values()):
            raise RuntimeError(
                "Phase 6 job reconciliation failed: "
                + json.dumps(phase_6_validation, sort_keys=True)
            )

        self.print_completion(
            step_name="PHASE 6 — Document Manager",
            message=(
                f"{document_manager_report['job_count']} apply job(s) "
                "were evaluated for application materials.\n"
                f"{document_manager_report['ready_count']} have all "
                "identified originals available.\n"
                f"{document_manager_report['manual_review_count']} "
                "require manual review."
            ),
            elapsed_seconds=phase_6_elapsed,
        )

        report_elapsed = max(
            0.0,
            perf_counter()
            - report_start
            - phase_6_elapsed,
        )
        total_elapsed = perf_counter() - total_start

        summary_report = pipeline.save_summary_report(
            pipeline_result=pipeline_result,
            category_reports=category_reports,
            output_file=write_paths["summary"],
            job_board=job_board,
            run_started_at=run_started_at,
            phase_3_elapsed_time_sec=phase_3_elapsed,
            phase_6_elapsed_time_sec=phase_6_elapsed,
            report_writing_time_sec=report_elapsed,
            total_elapsed_time_sec=total_elapsed,
            report_files={
                **published_report_files,
                "apply_stats": published_paths["apply_stats"],
                "document_manager": published_paths[
                    "document_manager"
                ],
                "applied": published_paths["applied"],
                "summary": published_paths["summary"],
                "log": published_paths["log"],
            },
            pipeline_name=pipeline_name,
            additional_validation={
                f"phase_6_{name}": passed
                for name, passed in phase_6_validation.items()
            },
        )
        self._stamp_scope(summary_report)
        pipeline.save_report(summary_report, write_paths["summary"])

        validation = summary_report["validation"]
        if not all(validation.values()):
            raise RuntimeError(
                "Run completed, but summary reconciliation failed: "
                + json.dumps(validation, sort_keys=True)
            )

        return {
            "job_data_list": job_data_list,
            "pipeline_result": pipeline_result,
            "category_reports": category_reports,
            "summary_report": summary_report,
            "document_manager_report": document_manager_report,
            "report_paths": published_paths,
            "phase_3_elapsed_time_sec": phase_3_elapsed,
            "phase_6_elapsed_time_sec": phase_6_elapsed,
            "report_writing_time_sec": report_elapsed,
            "total_elapsed_time_sec": total_elapsed,
        }

    def run_transactional(
        self,
        *,
        staging_paths: dict[str, Path],
        live_paths: dict[str, Path],
        pipeline_name: str,
        report_title: str,
    ) -> dict:
        """Build and validate staged reports before publishing them."""

        staging_dir = staging_paths["report_dir"]
        live_dir = live_paths["report_dir"]
        self._reset_directory(staging_dir)

        try:
            result = self.run(
                write_paths=staging_paths,
                published_paths=live_paths,
                pipeline_name=pipeline_name,
                report_title=report_title,
            )
            self._publish_staged_reports(
                staging_dir,
                live_dir,
                staging_paths["applied"],
                live_paths["applied"],
            )
            return result
        finally:
            staging_applied = staging_paths["applied"]
            if (
                not staging_applied.is_relative_to(staging_dir)
                and staging_applied.exists()
            ):
                staging_applied.unlink()
            if staging_dir.exists():
                shutil.rmtree(staging_dir)

    def run_rpa_transactional(
        self,
        *,
        staging_paths: dict[str, Path],
        live_paths: dict[str, Path],
        pipeline_name: str,
        report_title: str,
    ) -> dict:
        """Run Phases 3–5 and preserve downstream published artifacts."""

        staging_dir = staging_paths["report_dir"]
        live_dir = live_paths["report_dir"]
        self._reset_directory(staging_dir)

        try:
            result = self.run(
                write_paths=staging_paths,
                published_paths=live_paths,
                pipeline_name=pipeline_name,
                report_title=report_title,
                include_downstream=False,
            )

            # RPA does not analyze application materials, but it does apply
            # manual history maintenance so applied and expired records leave
            # the active Document Manager report immediately.
            if live_paths["document_manager"].is_file():
                staging_paths["document_manager"].parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                document_report = self._load_optional_report(
                    live_paths["document_manager"]
                )
                retained = result["application_history"][
                    "retained_document_plans"
                ]
                document_report["jobs"] = retained
                document_report["job_count"] = len(retained)
                document_report["ready_count"] = sum(
                    bool(plan.get("ready")) for plan in retained
                )
                document_report["missing_documents_count"] = sum(
                    bool(plan.get("missing_documents"))
                    for plan in retained
                )
                document_report["manual_review_count"] = sum(
                    bool(plan.get("manual_review_required"))
                    for plan in retained
                )
                document_report.setdefault("report_metadata", {})[
                    "last_job_sequence_number"
                ] = result["application_history"][
                    "last_job_sequence_number"
                ]
                staging_paths["document_manager"].write_text(
                    json.dumps(
                        document_report,
                        indent=2,
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            self._publish_staged_reports(
                staging_dir,
                live_dir,
                staging_paths["applied"],
                live_paths["applied"],
            )
            return result
        finally:
            staging_applied = staging_paths["applied"]
            if (
                not staging_applied.is_relative_to(staging_dir)
                and staging_applied.exists()
            ):
                staging_applied.unlink()
            if staging_dir.exists():
                shutil.rmtree(staging_dir)

    def run_document_manager(
        self,
        *,
        apply_report_path: Path,
        staging_output: Path,
        staging_summary: Path,
        staging_apply: Path,
        staging_applied: Path,
        published_output: Path,
        published_summary: Path,
        published_applied: Path,
        published_closed: Path,
        job_board: str,
        pipeline_name: str,
        staging_apply_stats: Path | None = None,
        published_apply_stats: Path | None = None,
    ) -> dict:
        """Run and transactionally publish only Phase 6."""

        phase_start = perf_counter()
        run_started_at = datetime.now().astimezone()
        document_manager = self.create_document_manager()

        staging_apply_stats = staging_apply_stats or staging_apply.with_name(
            ".document_manager_apply_stats_staging.txt"
        )
        published_apply_stats = (
            published_apply_stats
            or apply_report_path.with_name("apply_jobs_stats.txt")
        )

        staging_files = (
            staging_output,
            staging_summary,
            staging_apply,
            staging_applied,
            staging_apply_stats,
        )
        for staging_file in staging_files:
            if staging_file.exists():
                staging_file.unlink()
        staging_output.parent.mkdir(parents=True, exist_ok=True)

        try:
            apply_jobs = document_manager.load_apply_jobs(
                apply_report_path
            )
            provisioner = self.create_provisioner()
            stale_urls = {
                job["source_url"]
                for job in apply_jobs
                if job.get("source_url")
                and provisioner.should_discard_stale_posting(job)
            }
            history = ApplicationHistory().reconcile(
                apply_jobs,
                previous_apply_report=self._load_optional_report(
                    apply_report_path
                ),
                previous_document_report=self._load_optional_report(
                    published_output
                ),
                previous_applied_report=self._load_optional_report(
                    published_applied
                ),
                privately_suppressed_urls=(
                    self._report_urls(
                        self._load_optional_report(published_closed)
                    )
                    | stale_urls
                ),
                job_board=job_board,
                pipeline_name=pipeline_name,
                remote=self.remote,
            )
            posting_results = self.load_document_postings(
                history["new_apply_jobs"]
            )
            application_plans = document_manager.build_application_plans(
                posting_results
            )
            application_plans = (
                history["retained_document_plans"] + application_plans
            )
            report = document_manager.save_document_manager_report(
                application_plans,
                staging_output,
                apply_jobs=history["apply_jobs"],
                job_board=job_board,
                run_started_at=run_started_at,
                pipeline_name=pipeline_name,
            )
            self._stamp_scope(report)
            report["report_metadata"]["last_job_sequence_number"] = history[
                "last_job_sequence_number"
            ]
            staging_output.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            apply_report = self._load_optional_report(apply_report_path)
            apply_report["jobs"] = history["apply_jobs"]
            apply_report["job_count"] = len(history["apply_jobs"])
            staging_apply.write_text(
                json.dumps(apply_report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            JobPipeline.save_apply_jobs_stats(
                history["apply_jobs"],
                staging_apply_stats,
            )
            staging_applied.write_text(
                json.dumps(
                    history["applied_report"],
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            validation = report["validation"]
            if not all(validation.values()):
                raise RuntimeError(
                    "Phase 6 job reconciliation failed: "
                    + json.dumps(validation, sort_keys=True)
                )

            summary = json.loads(
                published_summary.read_text(encoding="utf-8")
            )
            # Phase 7 application-document generation was retired. An
            # isolated Document Manager run also removes its legacy summary
            # timing and validation fields from previously published reports.
            summary.get("timing", {}).pop(
                "phase_7_elapsed_time",
                None,
            )
            validation_summary = summary.setdefault("validation", {})
            for name in list(validation_summary):
                if name.startswith("phase_7_"):
                    del validation_summary[name]
            elapsed = perf_counter() - phase_start
            summary = self._update_summary_phase_timing(
                summary,
                "phase_6",
                elapsed,
            )
            self._stamp_scope(summary)
            summary["validation"].update(
                {
                    f"phase_6_{name}": passed
                    for name, passed in validation.items()
                }
            )
            staging_summary.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            self._publish_staged_files(
                (
                    (staging_output, published_output),
                    (staging_summary, published_summary),
                    (staging_apply, apply_report_path),
                    (staging_apply_stats, published_apply_stats),
                    (staging_applied, published_applied),
                )
            )
        finally:
            for staging_file in staging_files:
                if staging_file.exists():
                    staging_file.unlink()

        self.print_completion(
            step_name="PHASE 6 — Document Manager",
            message=(
                f"{report['job_count']} apply job(s) were evaluated "
                "from the existing Phase 5 report.\n"
                f"{report['ready_count']} have all identified originals "
                "available.\n"
                f"{report['manual_review_count']} require manual review."
            ),
            elapsed_seconds=elapsed,
        )

        return {
            "document_manager_report": report,
            "summary_report": summary,
            "document_manager_path": published_output,
            "phase_6_elapsed_time_sec": elapsed,
        }
