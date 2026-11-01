"""
Phases 3-4 - Live HigherEdJobs Provisioner Test
Validates deterministic provisioning of normalized live postings.
"""

import argparse

import json

from src.job_boards.higheredjobs.source import HigherEdJobsSource
from src.job_provisioner import JobProvisioner
from src.main import _private_data_path
from src.profile_loader import load_user_profile


parser = argparse.ArgumentParser()
parser.add_argument("--landing_url", required=True)
parser.add_argument("--private_data_path", required=True, type=_private_data_path)
arguments = parser.parse_args()
user_profile = load_user_profile(arguments.private_data_path)

source = HigherEdJobsSource(landing_url=arguments.landing_url)
provisioner = JobProvisioner(user_profile)

job_data_list = source.load_jobs(limit=3)

if not job_data_list:
    raise RuntimeError(
        "Phase 3 returned no HigherEdJobs job records."
    )

passed_jobs = []
skipped_jobs = []
manual_review_jobs = []

for job_data in job_data_list:
    source_url = job_data.get("source_url")

    assert source_url, (
        "Phase 3 job record does not preserve source_url."
    )

    if job_data.get("manual_review_required"):
        manual_review_jobs.append(
            {
                **job_data,
                "final_recommendation": "manual_review",
            }
        )

        continue

    provision_result = provisioner.evaluate(job_data)
    provisioned_job = provision_result["job_data"]

    assert provisioned_job.get("source_url") == source_url

    if provision_result["passed_provisioner"]:
        passed_jobs.append(provisioned_job)

    else:
        skip_record = provisioner.create_skip_record(
            provisioned_job,
            provision_result["reasons"],
        )

        assert skip_record["source_url"] == source_url
        assert skip_record["final_recommendation"] == "skip"
        assert skip_record["skipped_before_llm"] is True

        skipped_jobs.append(skip_record)


print("\n" + "=" * 60)
print("Phase 3–4 HigherEdJobs Integration Results")
print("=" * 60)

print(f"Jobs received from Phase 3 : {len(job_data_list)}")
print(f"Passed Phase 4             : {len(passed_jobs)}")
print(f"Skipped by Phase 4         : {len(skipped_jobs)}")
print(f"Manual review              : {len(manual_review_jobs)}")

print("\nProcessed records:")

print(
    json.dumps(
        {
            "passed_jobs": passed_jobs,
            "skipped_jobs": skipped_jobs,
            "manual_review_jobs": manual_review_jobs,
        },
        indent=4,
    )
)

assert (
    len(passed_jobs)
    + len(skipped_jobs)
    + len(manual_review_jobs)
    == len(job_data_list)
)

print(
    "\nLive HigherEdJobs Phase 3–4 integration passed."
)
