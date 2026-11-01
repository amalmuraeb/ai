"""
Phase 4 - Job Provisioner Test
Validates deterministic filtering and skip-record behavior.
"""

from datetime import date, timedelta

from src.job_provisioner import JobProvisioner
from src.test.data.job_provisioner_cases import TEST_CASES
from src.test.data.user_profile import TEST_USER_PROFILE

provisioner = JobProvisioner(TEST_USER_PROFILE)
today = date.today()


def make_job(**overrides):
    """
    Return a valid baseline normalized job record.
    """

    job = {
        "title": "Assistant Professor of Electrical Engineering",
        "company": "Example University",
        "city": "Example City",
        "state": "MI",
        "country": "US",
        "salary": "$130,000 - $160,000",
        "employment_type": "full-time",
        "posting_date": today.strftime("%Y-%m-%d"),
        "closing_date": (
            today + timedelta(days=730)
        ).strftime("%Y-%m-%d"),
        "raw_text": (
            "Assistant Professor of Electrical Engineering. "
            "This is a full-time faculty position involving "
            "embedded systems and computer engineering."
        ),
    }

    closing_date_offset_days = overrides.pop(
        "closing_date_offset_days",
        None,
    )

    if closing_date_offset_days is not None:
        job["closing_date"] = (
            today + timedelta(days=closing_date_offset_days)
        ).strftime("%Y-%m-%d")

    job.update(overrides)

    return job


failures = []

for case in TEST_CASES:
    job = make_job(**case["overrides"])
    expected = case["expected"]

    result = provisioner.evaluate(job)
    provisioned_job = result["job_data"]

    try:
        assert result["passed_provisioner"] is expected["passed"]

        assert provisioned_job["salary_min"] == expected["salary_min"]
        assert provisioned_job["salary_max"] == expected["salary_max"]
        assert provisioned_job["salary_match"] is expected["salary_match"]

        assert (
            provisioned_job["employment_type_match"]
            is expected["employment_type_match"]
        )

        expected_reason = expected["reason_contains"]

        if expected_reason is None:
            assert result["reasons"] == []
        else:
            assert any(
                expected_reason in reason
                for reason in result["reasons"]
            )

        expected_warning = expected["warning_contains"]

        if expected_warning is None:
            assert result["warnings"] == []
        else:
            assert any(
                expected_warning in warning
                for warning in result["warnings"]
            )

        print(f'PASS: {case["name"]}')

    except AssertionError:
        failures.append(
            {
                "name": case["name"],
                "job": job,
                "expected": expected,
                "result": result,
            }
        )

        print(f'FAIL: {case["name"]}')

skip_input = make_job(
    title="Postdoctoral Associate",
    company="Example University",
    source_url="https://www.higheredjobs.com/faculty/details.cfm?JobCode=123456",
)

skip_evaluation = provisioner.evaluate(skip_input)

skip_record = provisioner.create_skip_record(
    skip_evaluation["job_data"],
    skip_evaluation["reasons"],
)

try:
    assert skip_record["title"] == "Postdoctoral Associate"
    assert skip_record["company"] == "Example University"

    assert (
        skip_record["source_url"]
        == "https://www.higheredjobs.com/faculty/details.cfm?JobCode=123456"
    )

    assert skip_record["final_recommendation"] == "skip"
    assert skip_record["skipped_before_llm"] is True

    assert any(
        "Excluded role" in reason
        for reason in skip_record["skip_reasons"]
    )

    print("PASS: skip record preserves required fields")

except AssertionError:
    failures.append(
        {
            "name": "skip record preserves required fields",
            "result": skip_record,
        }
    )

    print("FAIL: skip record preserves required fields")

print()

table_case_failures = [
    failure
    for failure in failures
    if failure["name"] != "skip record preserves required fields"
]

skip_record_failed = any(
    failure["name"] == "skip record preserves required fields"
    for failure in failures
)

stale_rule_date = date(2026, 9, 7)
stale_rule_cases = (
    (
        "one-to-two-year posting without closing date",
        {"posting_date": "2025-03-01 12:00:00", "closing_date": None},
        True,
    ),
    (
        "one-to-two-year posting with acceptable closing date",
        {
            "posting_date": "2025-03-01 12:00:00",
            "closing_date": "2027-04-01 23:59:59.9",
        },
        False,
    ),
    (
        "one-to-two-year posting with closing date too soon",
        {"posting_date": "2025-03-01", "closing_date": "2026-10-01"},
        True,
    ),
    (
        "posting at two-year maximum",
        {"posting_date": "2024-09-07", "closing_date": "2027-04-01"},
        True,
    ),
    (
        "recent posting without closing date",
        {"posting_date": "2026-01-01", "closing_date": None},
        False,
    ),
    (
        "missing posting date",
        {"posting_date": None, "closing_date": None},
        False,
    ),
)
for case_name, job, expected_discard in stale_rule_cases:
    try:
        assert provisioner.should_discard_stale_posting(
            job,
            run_date=stale_rule_date,
        ) is expected_discard
        print(f"PASS: {case_name}")
    except AssertionError:
        failures.append(
            {
                "name": case_name,
                "job": job,
                "expected": expected_discard,
            }
        )
        print(f"FAIL: {case_name}")

print(
    f"Provisioner cases passed: "
    f"{len(TEST_CASES) - len(table_case_failures)}"
)
print(f"Provisioner cases failed: {len(table_case_failures)}")

print(
    "Skip-record test: "
    + ("FAILED" if skip_record_failed else "PASSED")
)

if failures:
    print("\nFailure details:")

    for failure in failures:
        print(f'\nCase: {failure["name"]}')

        if "job" in failure:
            print(f'Job: {failure["job"]}')

        if "expected" in failure:
            print(f'Expected: {failure["expected"]}')

        print(f'Result: {failure["result"]}')

    raise AssertionError(
        f"{len(failures)} JobProvisioner test(s) failed."
    )

print("\nAll JobProvisioner tests passed.")
