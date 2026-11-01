"""
Phase 6 - Document Manager Test
Validates extraction, fallback, inventory matching, and reporting.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.document_manager import DocumentManager


EXAMPLE_JOB = {
    "title": "Example Faculty Position",
    "company": "Example University",
    "city": "Example City",
    "state": "EX",
    "source_url": (
        "https://example.test/jobs/example-faculty-position"
    ),
    "final_recommendation": "apply",
}

EXAMPLE_POSTING_TEXT = (
    "Application Instructions\n"
    "Applicants should submit a cover letter, curriculum vitae, personal "
    "statement to include philosophy and plans for research, teaching and "
    "service, as applicable, and a list of four references (including postal "
    "addresses, phone numbers and email addresses) by applying for this "
    "specific position at\n"
    "https://example.test/apply/example-faculty-position\n"
    "Additional materials may be requested from finalists."
)


class FakeRequirementAgent:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def detect(self, posting_text, **options):
        self.calls += 1
        return self.result


def main():
    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        docs_root = temp_root / "required_documents" / "original"
        for category in DocumentManager.CATEGORIES:
            (docs_root / category).mkdir(parents=True)

        # Placeholder files test discovery only; private real documents are
        # never read, copied, or added to the repository regression fixtures.
        (docs_root / "cv" / "cv_master.docx").write_text(
            "test cv",
            encoding="utf-8",
        )
        # WSL may materialize Windows alternate-stream metadata as a regular
        # file. Its CV-like name must never supersede the real DOCX template.
        (docs_root / "cv" / "candidate_cv.docx:Zone.Identifier").write_text(
            "[ZoneTransfer]",
            encoding="utf-8",
        )
        (docs_root / "cv" / "~$cv_master.docx").write_text(
            "Word lock file",
            encoding="utf-8",
        )
        (docs_root / "dynamic" / "cover_letter_master.docx").write_text(
            "test cover letter",
            encoding="utf-8",
        )
        (docs_root / "dynamic" / "research_statement_master.docx").write_text(
            "test research statement",
            encoding="utf-8",
        )
        (docs_root / "dynamic" / "teaching_statement_master.docx").write_text(
            "test teaching statement",
            encoding="utf-8",
        )
        (docs_root / "static" / "references.docx").write_text(
            "test references",
            encoding="utf-8",
        )

        apply_report = temp_root / "apply_jobs.json"
        apply_report.write_text(
            json.dumps({"job_count": 1, "jobs": [EXAMPLE_JOB]}),
            encoding="utf-8",
        )

        manager = DocumentManager(docs_root)
        jobs = manager.load_apply_jobs(apply_report)
        job = manager.find_job(
            jobs,
            title="Example Faculty Position",
            company="Example University",
            city="Example City",
            state="EX",
        )
        plan = manager.build_application_plan(job, EXAMPLE_POSTING_TEXT)

        assert plan["job"]["company"] == "Example University"
        assert plan["job"]["state"] == "EX"
        assert plan["ready"] is False
        assert plan["missing_documents"] == ["personal_statement"]
        assert plan["manual_review_required"] is False
        assert plan["ollama_fallback_used"] is False
        assert plan["ollama_fallback_error"] is None
        assert plan["unclassified_requirements"] == []
        selected = {
            item["document_type"]: item["selected_template"]
            for item in plan["required_documents"]
        }
        assert selected["cv"]["name"] == "cv_master.docx"
        assert selected["cover_letter"]["name"] == (
            "cover_letter_master.docx"
        )
        assert selected["references"]["name"] == "references.docx"
        assert selected["personal_statement"] is None
        assert [
            item["document_type"] for item in plan["required_documents"]
        ] == [
            "cover_letter",
            "cv",
            "personal_statement",
            "references",
        ]
        assert "research, teaching and service" in next(
            item["posting_requirement"]
            for item in plan["required_documents"]
            if item["document_type"] == "personal_statement"
        )
        assert manager.summary() == {"cv": 1, "static": 1, "dynamic": 3}

        report_path = temp_root / "reports" / "document_manager.json"
        report = manager.save_document_manager_report(
            [plan],
            report_path,
            apply_jobs=[job],
            job_board="higheredjobs_html",
            pipeline_name="Document Manager Regression",
        )
        loaded_report = json.loads(report_path.read_text(encoding="utf-8"))
        assert loaded_report == report
        assert report["report_metadata"]["report_name"] == (
            "document_manager.json"
        )
        assert report["job_count"] == 1
        assert report["ready_count"] == 0
        assert report["missing_documents_count"] == 1
        assert report["manual_review_count"] == 0
        assert "job_sequence_number" not in plan["job"]
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

        ambiguous_text = (
            "Application details are provided below. A complete application "
            "consists of a letter of interest and an academic vita."
        )
        evidence = (
            "A complete application consists of a letter of interest and "
            "an academic vita."
        )
        fallback_agent = FakeRequirementAgent(
            {
                "analysis_complete": True,
                "requirements": [
                    {
                        "document_type": "cover_letter",
                        "posting_requirement": evidence,
                    },
                    {
                        "document_type": "cv",
                        "posting_requirement": evidence,
                    },
                ],
                "unresolved_requirements": [],
            }
        )
        fallback_manager = DocumentManager(
            docs_root,
            requirement_agent=fallback_agent,
        )
        fallback_plan = fallback_manager.build_application_plan(
            job,
            ambiguous_text,
        )
        assert fallback_agent.calls == 1
        assert fallback_plan["ollama_fallback_used"] is True
        assert fallback_plan["ollama_fallback_error"] is None
        assert fallback_plan["manual_review_required"] is False
        assert fallback_plan["ready"] is True
        assert [
            item["document_type"]
            for item in fallback_plan["required_documents"]
        ] == ["cover_letter", "cv"]

        formatting_agent = FakeRequirementAgent(
            {
                "analysis_complete": True,
                "requirements": [
                    {
                        "document_type": "cv",
                        "posting_requirement": (
                            "Submit a curriculum vitae and cover letter."
                        ),
                    }
                ],
                "unresolved_requirements": [],
            }
        )
        formatting_plan = DocumentManager(
            docs_root,
            requirement_agent=formatting_agent,
        ).build_application_plan(
            job,
            "Application details:\nSubmit a curriculum vitae—and cover letter.",
        )
        assert formatting_plan["manual_review_required"] is False
        assert formatting_plan["required_documents"][0][
            "posting_requirement"
        ] == "Submit a curriculum vitae—and cover letter"

        invalid_agent = FakeRequirementAgent(
            {
                "analysis_complete": True,
                "requirements": [
                    {
                        "document_type": "cover_letter",
                        "posting_requirement": evidence,
                    },
                    {
                        "document_type": "cv",
                        "posting_requirement": "Invented evidence",
                    }
                ],
                "unresolved_requirements": [],
            }
        )
        invalid_plan = DocumentManager(
            docs_root,
            requirement_agent=invalid_agent,
        ).build_application_plan(job, ambiguous_text)
        assert invalid_plan["manual_review_required"] is True
        assert invalid_plan["ready"] is False
        assert "exact posting quote" in invalid_plan[
            "ollama_fallback_error"
        ]
        assert [
            item["document_type"]
            for item in invalid_plan["required_documents"]
        ] == ["cover_letter"]

    print("Document-manager test passed.")


if __name__ == "__main__":
    main()
