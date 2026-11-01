"""
Phases 3-6 - Sample-HTML Full Pipeline Test
Validates shared orchestration offline with deterministic test doubles.
"""

import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlparse

from src.config.report_paths import build_report_paths
from src.document_manager import DocumentManager
from src.job_boards.higheredjobs.reader import HigherEdJobsReader
from src.job_boards.higheredjobs.runner import HigherEdJobsRunner
from src.job_agent_runner import JobAgentRunner
from src.job_provisioner import JobProvisioner
from src.test.data.user_profile import TEST_USER_PROFILE


FIXTURE_DIR = Path("input/job_boards/higheredjobs")
EXPECTED_SCORES = (95, 80)


class SampleHtmlHigherEdJobsSource:
    """Load normalized job records from repository HTML fixtures."""

    def __init__(self, fixture_dir: Path):
        self.fixture_dir = fixture_dir
        self.reader = HigherEdJobsReader()

    def load_jobs(self) -> list[dict]:
        html_paths = sorted(self.fixture_dir.glob("*.html"))

        if not html_paths:
            raise RuntimeError(
                f"No HigherEdJobs HTML fixtures found in {self.fixture_dir}."
            )

        return [
            self.reader.from_html(
                html_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ),
                source_url=html_path.resolve().as_uri(),
            )
            for html_path in html_paths
        ]


class DeterministicAnalysisAgent:
    """Return stable fit scores without contacting Ollama."""

    def __init__(self, scores: tuple[int, ...]):
        self.scores = iter(scores)
        self.calls = 0

    def run(self, analysis_text: str) -> str:
        self.calls += 1

        try:
            fit_score = next(self.scores)
        except StopIteration as error:
            raise AssertionError(
                "More jobs reached the analysis agent than expected."
            ) from error

        return json.dumps(
            {
                "fit_score": fit_score,
                "match_level": "test",
                "focus_areas": [
                    "embedded and intelligent computing",
                    "computer engineering education",
                ],
                "must_have_skills": [],
                "missing_skills": [],
                "discipline_match": True,
                "risk_flags": [],
            }
        )


class DeterministicProvisioner(JobProvisioner):
    """Pin posting-age evaluation so fixtures do not age with the calendar."""

    def should_discard_stale_posting(self, job_data, run_date=None):
        return super().should_discard_stale_posting(
            job_data,
            run_date=date(2026, 9, 7),
        )


class SampleHtmlHigherEdJobsRunner(HigherEdJobsRunner):
    """Run HigherEdJobs production orchestration with test doubles."""

    def __init__(self, fixture_dir: Path):
        JobAgentRunner.__init__(self, TEST_USER_PROFILE)
        self.fixture_dir = fixture_dir
        self.analysis_agent = DeterministicAnalysisAgent(
            EXPECTED_SCORES
        )

    def create_source(self) -> SampleHtmlHigherEdJobsSource:
        return SampleHtmlHigherEdJobsSource(self.fixture_dir)

    def create_agent(self) -> DeterministicAnalysisAgent:
        return self.analysis_agent

    def create_provisioner(self) -> DeterministicProvisioner:
        return DeterministicProvisioner(self.user_profile)

    def create_document_manager(self) -> DocumentManager:
        """Keep Phase 6 offline; ambiguous fixtures remain manual review."""
        return DocumentManager()

    def analysis_service_name(self) -> str:
        return "the deterministic test agent"

    def load_document_postings(self, apply_jobs):
        """Load Phase 6 posting bodies from the same saved HTML fixtures."""
        posting_results = []

        for job in apply_jobs:
            source_url = job["source_url"]
            fixture_path = Path(unquote(urlparse(source_url).path))

            try:
                parsed = HigherEdJobsReader().from_html(
                    fixture_path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    ),
                    source_url=source_url,
                )
                posting_results.append(
                    {
                        "job": job,
                        "posting_text": parsed.get("raw_text"),
                        "retrieval_error": None,
                    }
                )
            except Exception as error:
                posting_results.append(
                    {
                        "job": job,
                        "posting_text": None,
                        "retrieval_error": (
                            f"{type(error).__name__}: {error}"
                        ),
                    }
                )

        return posting_results


def main() -> None:
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        runner = SampleHtmlHigherEdJobsRunner(FIXTURE_DIR)
        staging_paths = build_report_paths(
            temp_root / ".sample_html_staging"
        )
        published_paths = build_report_paths(
            temp_root / "sample_html_reports"
        )

        # Exercise replacement of an existing published run, not only
        # first-time publication into an empty destination.
        published_paths["report_dir"].mkdir(parents=True)
        previous_run_marker = (
            published_paths["report_dir"] / "previous_run.txt"
        )
        previous_run_marker.write_text("previous", encoding="utf-8")

        result = runner.run_transactional(
            staging_paths=staging_paths,
            live_paths=published_paths,
            pipeline_name="Sample-HTML E2E Pipeline",
            report_title="SAMPLE-HTML E2E PIPELINE LOG",
        )

        run_summary = result["pipeline_result"]["run_summary"]
        category_reports = result["category_reports"]
        summary = result["summary_report"]
        document_report = result["document_manager_report"]

        assert run_summary["jobs_discovered"] == 10
        # The current fixture set includes two eligible jobs, one inaccessible
        # page, and seven deterministic exclusions spanning role, institution,
        # and focus-area rules.
        assert run_summary["jobs_sent_to_llm"] == 2
        assert run_summary["jobs_skipped_before_llm"] == 8
        assert run_summary["jobs_failed_llm"] == 0
        assert runner.analysis_agent.calls == 2

        expected_counts = {
            "apply": 1,
            "review": 1,
            "do_not_apply": 0,
            "skipped": 7,
            "unreachable": 1,
        }
        actual_counts = {
            category: report["job_count"]
            for category, report in category_reports.items()
        }
        assert actual_counts == expected_counts
        assert all(
            job["remote?"] in {"Yes", "No"}
            for report in category_reports.values()
            for job in report["jobs"]
        )
        analyzed_jobs = (
            category_reports["apply"]["jobs"]
            + category_reports["review"]["jobs"]
        )
        assert all(
            job.get("apply_url", "").startswith("https://")
            for job in analyzed_jobs
        )
        assert all(
            list(job).index("apply_url")
            == list(job).index("source_url") + 1
            for job in analyzed_jobs
        )
        assert all(
            job["focus_areas"]
            == [
                "embedded and intelligent computing",
                "computer engineering education",
            ]
            for job in analyzed_jobs
        )
        assert all(summary["validation"].values())
        assert document_report["job_count"] == expected_counts["apply"]
        assert all(
            plan["job"]["remote?"] in {"Yes", "No"}
            for plan in document_report["jobs"]
        )
        assert all(document_report["validation"].values())
        for job in result["job_data_list"]:
            assert job["source_url"].startswith("file://")

        for name in (
            "apply",
            "apply_stats",
            "review",
            "do_not_apply",
            "skipped",
            "unreachable",
            "document_manager",
            "applied",
            "summary",
            "log",
        ):
            assert published_paths[name].is_file()

        stats_text = published_paths["apply_stats"].read_text(
            encoding="utf-8"
        )
        assert "State | Job sequence numbers" in stats_text

        assert not staging_paths["report_dir"].exists()
        assert not previous_run_marker.exists()
        assert not (
            published_paths["report_dir"].with_name(
                ".sample_html_reports_previous"
            )
        ).exists()
        assert all(
            ".sample_html_staging" not in report_path
            for report_path in summary["report_files"].values()
        )

        # The RPA mode excludes both a newly marked applied job and a manually
        # closed job before Phase 4, then removes both from repository reports.
        applied_url = category_reports["apply"]["jobs"][0]["source_url"]
        tracked_documents = json.loads(
            published_paths["document_manager"].read_text(encoding="utf-8")
        )
        tracked_documents["jobs"][0]["job"]["applied?"] = "Yes"
        tracked_documents["jobs"][0]["job"]["application_date"] = (
            "2026-08-08"
        )
        published_paths["document_manager"].write_text(
            json.dumps(tracked_documents),
            encoding="utf-8",
        )
        rpa_staging_paths = build_report_paths(
            temp_root / ".sample_html_rpa_staging"
        )
        closed_url = category_reports["review"]["jobs"][0]["source_url"]
        closed_path = temp_root / "private" / "closed_jobs.json"
        closed_path.parent.mkdir(parents=True)
        closed_path.write_text(
            json.dumps(
                {"jobs": [{"job": {"source_url": closed_url}}]}
            ),
            encoding="utf-8",
        )
        published_paths["closed"] = closed_path
        rpa_staging_paths["closed"] = closed_path
        rpa_runner = SampleHtmlHigherEdJobsRunner(FIXTURE_DIR)
        rpa_result = rpa_runner.run_rpa_transactional(
            staging_paths=rpa_staging_paths,
            live_paths=published_paths,
            pipeline_name="Sample-HTML RPA Pipeline",
            report_title="SAMPLE-HTML RPA PIPELINE LOG",
            append_existing_reports=True,
        )

        assert rpa_result["summary_report"]["report_metadata"][
            "pipeline"
        ] == "Sample-HTML RPA Pipeline"
        assert rpa_result["summary_report"]["timing"][
            "phase_6_elapsed_time"
        ] == "0 s"
        assert json.loads(
            published_paths["document_manager"].read_text(encoding="utf-8")
        )["jobs"] == []
        assert rpa_result["pipeline_result"]["run_summary"][
            "suppressed_closed_jobs"
        ] == 1
        assert rpa_result["pipeline_result"]["run_summary"][
            "suppressed_applied_duplicates"
        ] == 1
        assert rpa_runner.analysis_agent.calls == 0
        assert all(rpa_result["summary_report"]["validation"].values())
        assert all(
            job.get("source_url") not in {closed_url, applied_url}
            for report in rpa_result["category_reports"].values()
            for job in report["jobs"]
        )
        applied_archive = json.loads(
            published_paths["applied"].read_text(encoding="utf-8")
        )
        assert applied_archive["jobs"][0]["job"]["source_url"] == applied_url
        assert not rpa_staging_paths["report_dir"].exists()

    print("Sample-HTML full-pipeline regression test passed.")


if __name__ == "__main__":
    main()
