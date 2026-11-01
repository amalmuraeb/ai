"""
Phase 6 - Isolated Document Manager Test
Validates phase-only inputs, publication, and upstream preservation.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.document_manager import DocumentManager
from src.job_agent_runner import JobAgentRunner
from src.job_pipeline import parse_elapsed_time
from src.main import parse_arguments
from src.test.data.user_profile import TEST_USER_PROFILE


class IsolatedDocumentManagerRunner(JobAgentRunner):
    """Exercise Phase 6 without creating or loading a Phase 3 source."""

    def __init__(self, docs_root):
        super().__init__(TEST_USER_PROFILE)
        self.docs_root = docs_root
        self.source_requested = False

    def create_source(self):
        self.source_requested = True
        raise AssertionError("Isolated Phase 6 must not run Phase 3.")

    def create_document_manager(self):
        return DocumentManager(self.docs_root)

    def load_document_postings(self, apply_jobs):
        return [
            {
                "job": job,
                "posting_text": (
                    "Application Instructions\n"
                    "Applicants should submit a curriculum vitae."
                ),
                "retrieval_error": None,
            }
            for job in apply_jobs
        ]


def _job(source_url):
    return {
        "title": "Assistant Professor",
        "company": "Example University",
        "source_url": source_url,
        "final_recommendation": "apply",
        "focus_areas": ["Embedded systems"],
        "must_have_skills": ["Teaching experience"],
    }


def main():
    private_path_arguments = [
        "--private_data_path",
        "/tmp/job-agent-private/private_data",
    ]
    landing_url_arguments = [
        "--landing_url",
        "https://www.higheredjobs.com/myHigherEdJobs/Agent/"
        "viewagent.cfm?AgentID=123456",
    ]
    assert parse_arguments(
        [*private_path_arguments, *landing_url_arguments]
    ).document_manager is False
    assert parse_arguments(
        ["--document_manager", *private_path_arguments]
    ).document_manager is True
    assert parse_arguments(
        ["--rpa", *private_path_arguments, *landing_url_arguments]
    ).rpa is True

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        docs_root = root / "required_documents" / "original"
        (docs_root / "cv").mkdir(parents=True)
        (docs_root / "cv" / "cv_master.docx").write_text(
            "test cv",
            encoding="utf-8",
        )

        live_dir = root / "live_runs"
        analyzed_dir = live_dir / "analyzed"
        analyzed_dir.mkdir(parents=True)
        apply_path = analyzed_dir / "apply_jobs.json"
        apply_path.write_text(
            json.dumps({"jobs": [_job("https://example.test/job")]}),
            encoding="utf-8",
        )
        original_apply = apply_path.read_text(encoding="utf-8")

        summary_path = live_dir / "summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "report_metadata": {
                        "report_version": "1.1",
                        "report_created_at": "2026-01-01T00:00:00+00:00",
                    },
                    "timing": {
                        "phase_3_elapsed_time_sec": "3 s",
                        "phase_6_elapsed_time_sec": "2 s",
                        "phase_7_elapsed_time": "5 s",
                        "total_elapsed_time_sec": "10 s",
                    },
                    "validation": {
                        "phase_7_all_dynamic_documents_generated": True,
                    },
                }
            ),
            encoding="utf-8",
        )
        document_path = live_dir / "document_manager.json"
        document_path.write_text(
            json.dumps(
                {
                    "report_metadata": {
                        "last_job_sequence_number": 0,
                    },
                    "jobs": [],
                }
            ),
            encoding="utf-8",
        )
        applied_path = live_dir / "applied_jobs.json"
        staging_path = root / ".document_manager_staging.json"
        staging_summary = root / ".document_manager_summary_staging.json"
        staging_apply = root / ".document_manager_apply_staging.json"
        staging_applied = root / ".document_manager_applied_staging.json"
        stats_path = analyzed_dir / "apply_jobs_stats.txt"
        closed_path = root / "private" / "closed_jobs.json"

        runner = IsolatedDocumentManagerRunner(docs_root)
        result = runner.run_document_manager(
            apply_report_path=apply_path,
            staging_output=staging_path,
            staging_summary=staging_summary,
            staging_apply=staging_apply,
            staging_applied=staging_applied,
            published_output=document_path,
            published_summary=summary_path,
            published_applied=applied_path,
            published_closed=closed_path,
            job_board="test_board",
            pipeline_name="Isolated Phase 6 Regression",
        )

        report = json.loads(document_path.read_text(encoding="utf-8"))
        assert report == result["document_manager_report"]
        report_job = report["jobs"][0]["job"]
        assert list(report_job)[:4] == [
            "job_sequence_number",
            "title",
            "applied?",
            "application_date",
        ]
        assert report_job["job_sequence_number"] == 1
        assert report_job["applied?"] == "No"
        assert report_job["application_date"] is None
        assert all(report["validation"].values())
        updated_apply = json.loads(apply_path.read_text(encoding="utf-8"))
        assert updated_apply["jobs"][0]["job_sequence_number"] == 1
        assert "Unknown | 1" in stats_path.read_text(encoding="utf-8")
        assert json.loads(applied_path.read_text(encoding="utf-8"))[
            "jobs"
        ] == []
        assert runner.source_requested is False
        assert apply_path.read_text(encoding="utf-8") != original_apply
        updated_summary = json.loads(
            summary_path.read_text(encoding="utf-8")
        )
        assert updated_summary["report_metadata"]["report_version"] == "1.2"
        assert not any(
            name.endswith("_sec")
            for name in updated_summary["timing"]
        )
        assert "phase_6_elapsed_time" in updated_summary["timing"]
        assert "phase_7_elapsed_time" not in updated_summary["timing"]
        assert not any(
            name.startswith("phase_7_")
            for name in updated_summary["validation"]
        )
        assert parse_elapsed_time(
            updated_summary["timing"]["total_elapsed_time"]
        ) < 10
        assert all(
            updated_summary["validation"][name]
            for name in updated_summary["validation"]
            if name.startswith("phase_6_")
        )
        assert not staging_path.exists()
        assert not staging_summary.exists()

        report["jobs"][0]["job"]["applied?"] = "Yes"
        report["jobs"][0]["job"]["application_date"] = "2026-08-08"
        document_path.write_text(
            json.dumps(report),
            encoding="utf-8",
        )
        runner.run_document_manager(
            apply_report_path=apply_path,
            staging_output=staging_path,
            staging_summary=staging_summary,
            staging_apply=staging_apply,
            staging_applied=staging_applied,
            published_output=document_path,
            published_summary=summary_path,
            published_applied=applied_path,
            published_closed=closed_path,
            job_board="test_board",
            pipeline_name="Applied Archive Regression",
        )
        assert json.loads(apply_path.read_text(encoding="utf-8"))[
            "jobs"
        ] == []
        assert stats_path.read_text(encoding="utf-8") == (
            "State | Job sequence numbers\n"
            "------+---------------------\n"
        )
        assert json.loads(document_path.read_text(encoding="utf-8"))[
            "jobs"
        ] == []
        archived = json.loads(applied_path.read_text(encoding="utf-8"))
        assert archived["job_count"] == 1
        assert archived["jobs"][0]["job"]["application_date"] == (
            "2026-08-08"
        )
        assert archived["jobs"][0]["job"]["focus_areas"] == [
            "Embedded systems"
        ]
        assert archived["jobs"][0]["job"]["must_have_skills"] == [
            "Teaching experience"
        ]
        assert set(archived["jobs"][0]) == {"job"}

        invalid_report = {
            "jobs": [
                {
                    "source_url": "https://example.test/invalid",
                    "final_recommendation": "apply",
                }
            ]
        }
        apply_path.write_text(
            json.dumps(invalid_report),
            encoding="utf-8",
        )
        previous_report = document_path.read_text(encoding="utf-8")
        previous_summary = summary_path.read_text(encoding="utf-8")

        try:
            runner.run_document_manager(
                apply_report_path=apply_path,
                staging_output=staging_path,
                staging_summary=staging_summary,
                staging_apply=staging_apply,
                staging_applied=staging_applied,
                published_output=document_path,
                published_summary=summary_path,
                published_applied=applied_path,
                published_closed=closed_path,
                job_board="test_board",
                pipeline_name="Failed Isolated Phase 6 Regression",
            )
        except ValueError as error:
            assert "missing required field" in str(error)
        else:
            raise AssertionError("Invalid Phase 6 report must not publish.")

        assert document_path.read_text(encoding="utf-8") == previous_report
        assert summary_path.read_text(encoding="utf-8") == previous_summary
        assert not staging_path.exists()
        assert not staging_summary.exists()
        assert not staging_apply.exists()
        assert not staging_applied.exists()

    print("Isolated document-manager test passed.")


if __name__ == "__main__":
    main()
