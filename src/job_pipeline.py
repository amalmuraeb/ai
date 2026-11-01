"""
Phases 3-5 - Job Pipeline
Coordinates provisioning, LLM analysis, metrics, and outcome reports.
"""

import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

from src.config.report_paths import DEBUG_SEPARATOR_WIDTH


def format_elapsed_time(elapsed_seconds: float) -> str:
    """Return seconds as a compact, human-readable duration."""

    rounded_seconds = round(float(elapsed_seconds), 2)
    hours = int(rounded_seconds // 3600)
    remaining_seconds = rounded_seconds - hours * 3600
    minutes = int(remaining_seconds // 60)
    seconds = round(remaining_seconds - minutes * 60, 2)
    seconds_text = f"{seconds:.2f}".rstrip("0").rstrip(".")

    if hours:
        return f"{hours} h {minutes} m {seconds_text} s"

    if minutes:
        return f"{minutes} m {seconds_text} s"

    return f"{seconds_text} s"


def parse_elapsed_time(duration: str) -> float:
    """Convert the report's human-readable duration back to seconds."""

    parts = str(duration).split()
    if len(parts) % 2:
        raise ValueError(f"Invalid elapsed-time value: {duration}")

    multipliers = {"h": 3600, "m": 60, "s": 1}
    elapsed_seconds = 0.0
    for index in range(0, len(parts), 2):
        value = float(parts[index])
        unit = parts[index + 1]
        if unit not in multipliers:
            raise ValueError(f"Invalid elapsed-time unit: {unit}")
        elapsed_seconds += value * multipliers[unit]

    return elapsed_seconds


class JobPipeline:

    def __init__(
        self,
        reader,
        provisioner,
        agent,
        user_profile,
        debug_log_file: Path | None = None
    ):
        self.reader = reader
        self.provisioner = provisioner
        self.agent = agent
        self.user_profile = user_profile
        self.debug_log_file = debug_log_file

    def run(self, job_data_list):
        """
        Process job postings through deterministic provisioning
        and LLM analysis while collecting separate Phase 4 and
        Phase 5 elapsed-time measurements.
        """

        start_time = perf_counter()

        results = []

        jobs_sent_to_llm = 0
        jobs_skipped_before_llm = 0
        jobs_failed_llm = 0

        phase_4_elapsed = 0.0
        phase_5_elapsed = 0.0

        for source_index, job_input in enumerate(
            job_data_list,
            start=1
        ):

            if isinstance(job_input, dict):
                job_data = job_input
            else:
                job_data = self.reader.from_text(job_input)

            self._write_debug_job_header(
                source_index=source_index,
                total_jobs=len(job_data_list),
                job_data=job_data
            )

            if job_data.get("manual_review_required"):

                self._write_debug(
                    "Skipped before Phase 4: manual review required. "
                    f"Page status: {job_data.get('page_status')}"
                )

                results.append(
                    self.create_manual_review_record(job_data)
                )

                jobs_skipped_before_llm += 1

                continue

            phase_4_start = perf_counter()
            self._write_debug("Phase 4 evaluation started.")

            try:
                provision_result = self.provisioner.evaluate(job_data)
            finally:
                phase_4_job_elapsed = (
                    perf_counter() - phase_4_start
                )
                phase_4_elapsed += phase_4_job_elapsed
                self._write_debug(
                    "Phase 4 evaluation completed "
                    f"({phase_4_job_elapsed:.2f} sec)."
                )

            if not provision_result["passed_provisioner"]:

                self._write_debug(
                    "Skipped before Phase 5. Reasons: "
                    + "; ".join(provision_result["reasons"])
                )

                skip_record = self.provisioner.create_skip_record(
                    provision_result["job_data"],
                    provision_result["reasons"]
                )

                jobs_skipped_before_llm += 1

                results.append(skip_record)

                continue

            job_data = provision_result["job_data"]

            jobs_sent_to_llm += 1

            phase_5_start = perf_counter()
            analysis_text = self.reader.to_analysis_text(job_data)

            self._write_debug(
                "Phase 5 Ollama request started. "
                f"Prompt size: {len(analysis_text)} characters."
            )

            try:
                result = self.agent.run(analysis_text)

                if not isinstance(result, str) or not result.strip():
                    raise ValueError(
                        "Ollama returned an empty response."
                    )

                result_dict = json.loads(result)

                if not isinstance(result_dict, dict):
                    raise ValueError(
                        "Ollama response was valid JSON but not "
                        "a JSON object."
                    )

            except KeyboardInterrupt:
                self._write_debug(
                    "Phase 5 Ollama request interrupted by user "
                    f"after {perf_counter() - phase_5_start:.2f} sec."
                )
                raise

            except Exception as ex:
                jobs_failed_llm += 1

                self._write_debug(
                    "Phase 5 Ollama request failed "
                    f"after {perf_counter() - phase_5_start:.2f} sec. "
                    f"{type(ex).__name__}: {ex}"
                )

                results.append(
                    self.create_llm_failure_record(
                        job_data=job_data,
                        error=ex
                    )
                )

                continue

            finally:
                phase_5_job_elapsed = (
                    perf_counter() - phase_5_start
                )
                phase_5_elapsed += phase_5_job_elapsed

            self._write_debug(
                "Phase 5 Ollama request completed "
                f"({phase_5_job_elapsed:.2f} sec). "
                f"Response size: {len(result)} characters."
            )

            result_dict.pop("final_recommendation", None)

            # Phase 5 is the authoritative source of structured focus areas
            # used by downstream document tailoring. Normalize imperfect LLM
            # output so every analyzed report exposes a stable list schema.
            focus_areas = result_dict.get("focus_areas", [])
            if not isinstance(focus_areas, list):
                focus_areas = []
            result_dict["focus_areas"] = list(
                dict.fromkeys(
                    area.strip()
                    for area in focus_areas
                    if isinstance(area, str) and area.strip()
                )
            )

            # Preserve source-authoritative identity and posting metadata for
            # reports and downstream phases. LLM output must not be required
            # to repeat fields already normalized by Phase 3.
            for field in (
                "title",
                "company",
                "city",
                "state",
                "posting_date",
                "closing_date",
                "remote?",
                "source_url",
                "apply_url",
            ):
                result_dict[field] = job_data.get(field)

            result_dict["salary_match"] = job_data.get(
                "salary_match"
            )
            result_dict["employment_type_match"] = job_data.get(
                "employment_type_match"
            )
            result_dict["is_closing_date_soon"] = job_data.get(
                "is_closing_date_soon"
            )

            apply_threshold = self.user_profile[
                "ranking_constraints"
            ]["apply_min_fit_score"]

            review_threshold = self.user_profile[
                "ranking_constraints"
            ]["review_min_fit_score"]

            try:
                fit_score = int(result_dict.get("fit_score", 0))
            except (TypeError, ValueError):
                fit_score = 0

            if fit_score >= apply_threshold:
                result_dict["final_recommendation"] = "apply"
            elif fit_score >= review_threshold:
                result_dict["final_recommendation"] = "review"
            else:
                result_dict["final_recommendation"] = "skip"

            existing_risk_flags = result_dict.get(
                "risk_flags",
                []
            )

            for warning in provision_result["warnings"]:
                if warning not in existing_risk_flags:
                    existing_risk_flags.append(warning)

            result_dict["risk_flags"] = existing_risk_flags

            results.append(result_dict)

        elapsed_time = perf_counter() - start_time

        average_llm_time = (
            phase_5_elapsed / jobs_sent_to_llm
            if jobs_sent_to_llm > 0
            else 0
        )

        llm_utilization = (
            jobs_sent_to_llm / len(job_data_list) * 100
            if len(job_data_list) > 0
            else 0
        )

        pipeline_overhead = max(
            elapsed_time - phase_4_elapsed - phase_5_elapsed,
            0.0
        )

        run_summary = {
            "jobs_discovered": len(job_data_list),
            "jobs_sent_to_llm": jobs_sent_to_llm,
            "jobs_skipped_before_llm": jobs_skipped_before_llm,
            "jobs_failed_llm": jobs_failed_llm,
            "llm_utilization_percent": round(
                llm_utilization,
                1
            ),
            "elapsed_time_sec": round(elapsed_time, 2),
            "phase_4_elapsed_time_sec": round(
                phase_4_elapsed,
                2
            ),
            "phase_5_elapsed_time_sec": round(
                phase_5_elapsed,
                2
            ),
            "pipeline_overhead_time_sec": round(
                pipeline_overhead,
                2
            ),
            # Existing keys retained for compatibility with
            # current tests and previously generated reports.
            "total_llm_time_sec": round(
                phase_5_elapsed,
                2
            ),
            "reader_provisioner_time_sec": round(
                elapsed_time - phase_5_elapsed,
                2
            ),
            "average_llm_time_sec": round(
                average_llm_time,
                2
            )
        }

        return {
            "run_summary": run_summary,
            "jobs": results
        }

    def initialize_debug_report(
        self,
        total_jobs: int,
        job_board: str = "unknown",
        run_started_at: datetime | None = None,
        report_title: str = "E2E LIVE PIPELINE DEBUG REPORT",
    ) -> None:
        """Create a fresh debug report for the current run."""

        if self.debug_log_file is None:
            return

        self.debug_log_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        started_at = run_started_at or datetime.now().astimezone()

        header = (
            "=" * DEBUG_SEPARATOR_WIDTH
            + f"\n{report_title}\n"
            + "=" * DEBUG_SEPARATOR_WIDTH
            + "\nRun started: "
            + started_at.isoformat(timespec="seconds")
            + f"\nJob Board: {job_board}"
            + f"\nTotal jobs loaded: {total_jobs}\n"
        )

        self.debug_log_file.write_text(
            header,
            encoding="utf-8"
        )

    def _write_debug(self, message: str) -> None:
        """Append one timestamped line to the debug report."""

        if self.debug_log_file is None:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self.debug_log_file.open(
            "a",
            encoding="utf-8"
        ) as debug_file:
            debug_file.write(f"[{timestamp}] {message}\n")

    def _write_debug_job_header(
        self,
        source_index: int,
        total_jobs: int,
        job_data: dict
    ) -> None:
        """Write identifying information for the current job."""

        self._write_debug("-" * DEBUG_SEPARATOR_WIDTH)
        self._write_debug(
            f"Source record {source_index}/{total_jobs}"
        )
        self._write_debug(
            f"Title: {job_data.get('title') or 'Unknown'}"
        )
        self._write_debug(
            f"Company: {job_data.get('company') or 'Unknown'}"
        )
        self._write_debug(
            f"URL: {job_data.get('source_url') or 'Unknown'}"
        )

    def save_report(self, report, output_file):
        """Save one pipeline report as formatted JSON."""

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=2)

    def partition_job_results(self, jobs):
        """
        Partition every pipeline result into one mutually exclusive
        report category.

        The current internal LLM recommendation value ``skip`` is
        written to ``do_not_apply_jobs.json``. Renaming that internal
        value is intentionally left for the separate terminology step.
        """

        partitions = {
            "apply": [],
            "review": [],
            "do_not_apply": [],
            "skipped": [],
            "unreachable": [],
        }

        for job in jobs:
            if job.get("skipped_before_llm") is True:
                partitions["skipped"].append(job)
                continue

            recommendation = job.get("final_recommendation")

            if recommendation == "apply":
                partitions["apply"].append(job)
            elif recommendation == "review":
                partitions["review"].append(job)
            elif recommendation in {"skip", "do_not_apply"}:
                partitions["do_not_apply"].append(job)
            else:
                partitions["unreachable"].append(job)

        partitioned_total = sum(
            len(category_jobs)
            for category_jobs in partitions.values()
        )

        if partitioned_total != len(jobs):
            raise RuntimeError(
                "Report partitioning did not preserve every job result."
            )

        return partitions

    def create_category_report(
        self,
        jobs,
        report_name: str,
        category: str,
        job_board: str = "unknown",
        run_started_at: datetime | None = None,
        pipeline_name: str = "End-to-End Live Pipeline",
    ):
        """Create one category-specific report with run metadata."""

        started_at = run_started_at or datetime.now().astimezone()
        created_at = datetime.now().astimezone()

        return {
            "report_metadata": {
                "report_name": report_name,
                "report_version": "1.0",
                "pipeline": pipeline_name,
                "job_board": job_board,
                "category": category,
                "run_started_at": started_at.isoformat(
                    timespec="seconds"
                ),
                "report_created_at": created_at.isoformat(
                    timespec="seconds"
                ),
            },
            "job_count": len(jobs),
            "jobs": jobs,
        }

    def save_partitioned_reports(
        self,
        pipeline_result,
        report_files,
        job_board: str = "unknown",
        run_started_at: datetime | None = None,
        pipeline_name: str = "End-to-End Live Pipeline",
    ):
        """
        Split a completed pipeline run and save the five category
        reports to their configured files.
        """

        partitions = self.partition_job_results(
            pipeline_result["jobs"]
        )

        required_categories = {
            "apply",
            "review",
            "do_not_apply",
            "skipped",
            "unreachable",
        }

        missing_categories = required_categories - set(report_files)
        if missing_categories:
            raise ValueError(
                "Missing report-file configuration for: "
                + ", ".join(sorted(missing_categories))
            )

        saved_reports = {}

        for category in sorted(required_categories):
            output_file = Path(report_files[category])
            report = self.create_category_report(
                jobs=partitions[category],
                report_name=output_file.name,
                category=category,
                job_board=job_board,
                run_started_at=run_started_at,
                pipeline_name=pipeline_name,
            )
            self.save_report(report, output_file)
            saved_reports[category] = report

        return saved_reports

    @staticmethod
    def create_apply_jobs_stats(jobs) -> str:
        """Return a readable state-to-sequence-number summary table."""
        jobs_by_state = {}
        for job in jobs:
            state = str(job.get("state") or "Unknown").strip() or "Unknown"
            sequence_number = job.get("job_sequence_number")
            if not isinstance(sequence_number, int):
                continue
            jobs_by_state.setdefault(state, []).append(sequence_number)

        rows = [
            (
                state,
                ", ".join(
                    str(number)
                    for number in sorted(set(jobs_by_state[state]))
                ),
            )
            for state in sorted(jobs_by_state, key=str.casefold)
        ]
        state_width = max(
            [len("State"), *(len(state) for state, _ in rows)]
        )
        header = f"{'State':<{state_width}} | Job sequence numbers"
        separator = f"{'-' * state_width}-+---------------------"
        body = [
            f"{state:<{state_width}} | {numbers}"
            for state, numbers in rows
        ]
        return "\n".join((header, separator, *body)) + "\n"

    @classmethod
    def save_apply_jobs_stats(cls, jobs, output_file) -> None:
        """Write the derived apply-job state summary beside apply_jobs.json."""
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            cls.create_apply_jobs_stats(jobs),
            encoding="utf-8",
        )

    def create_summary_report(
        self,
        pipeline_result,
        category_reports,
        job_board: str = "unknown",
        run_started_at: datetime | None = None,
        phase_3_elapsed_time_sec: float = 0.0,
        phase_6_elapsed_time_sec: float = 0.0,
        report_writing_time_sec: float = 0.0,
        total_elapsed_time_sec: float | None = None,
        report_files=None,
        pipeline_name: str = "End-to-End Live Pipeline",
        additional_validation=None,
    ):
        """Create an aggregate summary for one complete pipeline run."""

        started_at = run_started_at or datetime.now().astimezone()
        created_at = datetime.now().astimezone()
        run_summary = pipeline_result["run_summary"]

        outcome_counts = {
            category: report["job_count"]
            for category, report in category_reports.items()
        }

        analyzed_total = (
            outcome_counts.get("apply", 0)
            + outcome_counts.get("review", 0)
            + outcome_counts.get("do_not_apply", 0)
        )
        accounted_total = sum(outcome_counts.values())
        discovered = run_summary["jobs_discovered"]
        sent_to_llm = run_summary["jobs_sent_to_llm"]
        skipped = run_summary["jobs_skipped_before_llm"]
        failed_llm = run_summary["jobs_failed_llm"]
        history_adjustment = run_summary.get(
            "history_accounting_adjustment",
            0,
        )
        history_analyzed_adjustment = run_summary.get(
            "history_analyzed_adjustment",
            0,
        )

        if total_elapsed_time_sec is None:
            total_elapsed_time_sec = (
                phase_3_elapsed_time_sec
                + run_summary["elapsed_time_sec"]
                + report_writing_time_sec
            )

        paths = {
            name: str(path)
            for name, path in (report_files or {}).items()
        }

        return {
            "report_metadata": {
                "report_name": "summary.json",
                "report_version": "1.2",
                "pipeline": pipeline_name,
                "job_board": job_board,
                "run_started_at": started_at.isoformat(
                    timespec="seconds"
                ),
                "report_created_at": created_at.isoformat(
                    timespec="seconds"
                ),
            },
            "job_counts": {
                "discovered": discovered,
                "sent_to_llm": sent_to_llm,
                "skipped_before_llm": skipped,
                "llm_failures": failed_llm,
                "suppressed_applied_duplicates": run_summary.get(
                    "suppressed_applied_duplicates",
                    0,
                ),
                "suppressed_closed_jobs": run_summary.get(
                    "suppressed_closed_jobs",
                    0,
                ),
                "discarded_stale_jobs": run_summary.get(
                    "discarded_stale_jobs",
                    0,
                ),
                "apply": outcome_counts.get("apply", 0),
                "review": outcome_counts.get("review", 0),
                "do_not_apply": outcome_counts.get(
                    "do_not_apply", 0
                ),
                "skipped": outcome_counts.get("skipped", 0),
                "unreachable": outcome_counts.get(
                    "unreachable", 0
                ),
                "analyzed": analyzed_total,
                "accounted_for": accounted_total,
            },
            "timing": {
                "phase_3_elapsed_time": format_elapsed_time(
                    phase_3_elapsed_time_sec
                ),
                "phase_4_elapsed_time": format_elapsed_time(
                    run_summary["phase_4_elapsed_time_sec"]
                ),
                "phase_5_elapsed_time": format_elapsed_time(
                    run_summary["phase_5_elapsed_time_sec"]
                ),
                "phase_6_elapsed_time": format_elapsed_time(
                    phase_6_elapsed_time_sec
                ),
                "pipeline_overhead_time": format_elapsed_time(
                    run_summary["pipeline_overhead_time_sec"]
                ),
                "report_writing_time": format_elapsed_time(
                    report_writing_time_sec
                ),
                "total_elapsed_time": format_elapsed_time(
                    total_elapsed_time_sec
                ),
                "average_llm_time": format_elapsed_time(
                    run_summary["average_llm_time_sec"]
                ),
                # Utilization is a percentage, not an elapsed duration.
                "llm_utilization_percent": run_summary[
                    "llm_utilization_percent"
                ],
            },
            "report_files": paths,
            "validation": {
                "all_jobs_accounted_for": (
                    accounted_total == discovered + history_adjustment
                ),
                "discovered_equals_sent_plus_skipped": (
                    discovered == sent_to_llm + skipped
                ),
                "llm_results_accounted_for": (
                    sent_to_llm
                    == analyzed_total
                    + failed_llm
                    - history_analyzed_adjustment
                ),
                **(additional_validation or {}),
            },
        }

    def save_summary_report(
        self,
        pipeline_result,
        category_reports,
        output_file,
        **summary_options,
    ):
        """Create and persist ``summary.json`` for one run."""

        summary = self.create_summary_report(
            pipeline_result=pipeline_result,
            category_reports=category_reports,
            report_files=summary_options.pop(
                "report_files", None
            ),
            **summary_options,
        )
        self.save_report(summary, output_file)
        return summary

    def create_llm_failure_record(self, job_data, error):
        """
        Preserve a job when Ollama fails or returns invalid JSON.
        """

        return {
            "title": job_data.get("title"),
            "company": job_data.get("company"),
            "source_url": job_data.get("source_url"),
            "remote?": job_data.get("remote?", "No"),
            "salary_match": job_data.get("salary_match"),
            "employment_type_match": job_data.get(
                "employment_type_match"
            ),
            "is_closing_date_soon": job_data.get(
                "is_closing_date_soon"
            ),
            "risk_flags": [
                "LLM analysis failed; manual review required."
            ],
            "focus_areas": [],
            "llm_error_type": type(error).__name__,
            "llm_error": str(error),
            "final_recommendation": "manual_review"
        }

    def create_manual_review_record(self, job_data):
        """
        Create a standardized manual-review record.
        """

        return {
            **job_data,
            "final_recommendation": "manual_review"
        }
