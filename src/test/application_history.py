"""
Phases 5-6 - Application History Test
Validates durable numbering, archival, duplicate suppression, and expiry.
"""

from datetime import date

from src.application_history import ApplicationHistory


def _apply_job(url, closing_date=None, sequence=None):
    job = {
        "title": f"Professor {url[-1]}",
        "company": "Example University",
        "closing_date": closing_date,
        "source_url": url,
        "final_recommendation": "apply",
        "focus_areas": ["Artificial Intelligence"],
        "must_have_skills": ["Research experience"],
    }
    return {"job_sequence_number": sequence, **job} if sequence else job


def _plan(job, applied="No"):
    return {
        "job": {
            "job_sequence_number": job["job_sequence_number"],
            "title": job["title"],
            "applied?": applied,
            "application_date": "2026-08-01" if applied == "Yes" else None,
            "company": job["company"],
            "closing_date": job["closing_date"],
            "source_url": job["source_url"],
        },
        "required_documents": [],
        "missing_documents": [],
        "manual_review_required": False,
        "ready": True,
    }


def main():
    active = _apply_job("https://example.test/1", "2026-09-01", 20)
    applied = _apply_job("https://example.test/2", "2026-09-01", 21)
    expired = _apply_job("https://example.test/3", "2026-07-01", 22)
    fresh = _apply_job("https://example.test/4", "2026-10-01")
    result = ApplicationHistory().reconcile(
        [active, applied, expired, fresh],
        previous_apply_report={"jobs": [active, applied, expired]},
        previous_document_report={
            "report_metadata": {"last_job_sequence_number": 22},
            "jobs": [_plan(active), _plan(applied, "Yes"), _plan(expired)],
        },
        today=date(2026, 8, 8),
    )

    assert [job["job_sequence_number"] for job in result["apply_jobs"]] == [20, 23]
    assert [job["source_url"] for job in result["new_apply_jobs"]] == [fresh["source_url"]]
    assert result["last_job_sequence_number"] == 23
    assert result["applied_report"]["job_count"] == 1
    assert result["applied_report"]["jobs"][0]["job"]["applied?"] == "Yes"
    archived_job = result["applied_report"]["jobs"][0]["job"]
    assert archived_job["focus_areas"] == ["Artificial Intelligence"]
    assert archived_job["must_have_skills"] == ["Research experience"]
    assert set(result["applied_report"]["jobs"][0]) == {"job"}
    assert expired["source_url"] not in {job["source_url"] for job in result["apply_jobs"]}

    later = ApplicationHistory().reconcile(
        [_apply_job("https://example.test/5", "2026-11-01")],
        previous_document_report={
            "report_metadata": {"last_job_sequence_number": 23},
            "jobs": [],
        },
        previous_applied_report=result["applied_report"],
        today=date(2026, 8, 8),
    )
    assert later["new_apply_jobs"][0]["job_sequence_number"] == 24

    excluded = ApplicationHistory().reconcile(
        [],
        previous_apply_report={"jobs": [active]},
        previous_document_report={"jobs": [_plan(active)]},
        deterministically_excluded_urls={active["source_url"]},
        today=date(2026, 8, 8),
    )
    assert excluded["apply_jobs"] == []
    assert excluded["retained_document_plans"] == []

    closed = ApplicationHistory().reconcile(
        [active, fresh],
        previous_apply_report={"jobs": [active]},
        previous_document_report={"jobs": [_plan(active)]},
        privately_suppressed_urls={active["source_url"], fresh["source_url"]},
        today=date(2026, 8, 8),
    )
    assert closed["apply_jobs"] == []
    assert closed["retained_document_plans"] == []
    assert closed["new_apply_jobs"] == []
    print("Application-history test passed.")


if __name__ == "__main__":
    main()
