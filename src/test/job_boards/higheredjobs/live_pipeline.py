"""
Phases 3-5 - Live HigherEdJobs Pipeline Test
Processes one eligible live posting through provisioning and Ollama.
"""

import argparse
import json

from src.config.job_boards import HIGHEREDJOBS
from src.job_analysis_agent import JobAnalysisAgent
from src.job_boards.higheredjobs.source import HigherEdJobsSource
from src.job_pipeline import JobPipeline
from src.job_provisioner import JobProvisioner
from src.main import _private_data_path
from src.profile_loader import load_user_profile

parser = argparse.ArgumentParser()
parser.add_argument("--landing_url", required=True)
parser.add_argument("--private_data_path", required=True, type=_private_data_path)
arguments = parser.parse_args()
user_profile = load_user_profile(arguments.private_data_path)

source = HigherEdJobsSource(landing_url=arguments.landing_url)
reader = source.reader
provisioner = JobProvisioner(user_profile)
agent = JobAnalysisAgent(user_profile)

pipeline = JobPipeline(
    reader=reader,
    provisioner=provisioner,
    agent=agent,
    user_profile=user_profile,
)

job_data_list = source.load_jobs(
    limit=HIGHEREDJOBS["JOB_POSTS_PER_PAGE"]
)

if not job_data_list:
    raise RuntimeError(
        "Phase 3 returned no HigherEdJobs job records."
    )


eligible_job = None
preselection_skip_reasons = []

for job_data in job_data_list:
    source_url = job_data.get("source_url")

    assert source_url, (
        "Phase 3 job record does not preserve source_url."
    )

    if job_data.get("manual_review_required"):
        continue

    provision_result = provisioner.evaluate(job_data)

    if provision_result["passed_provisioner"]:
        eligible_job = job_data
        break

    preselection_skip_reasons.append(
        {
            "title": job_data.get("title"),
            "company": job_data.get("company"),
            "source_url": source_url,
            "reasons": provision_result["reasons"],
        }
    )


if eligible_job is None:
    print("\n" + "=" * 60)
    print("Live HigherEdJobs Eligible-Job Search")
    print("=" * 60)

    print(f"Jobs inspected: {len(job_data_list)}")
    print("Eligible jobs: 0")

    print("\nProvisioner rejection summary:")

    print(
        json.dumps(
            preselection_skip_reasons,
            indent=4,
        )
    )

    raise RuntimeError(
        "No eligible live posting was found within the first "
        f"{len(job_data_list)} HigherEdJobs records."
    )


pipeline_result = pipeline.run([eligible_job])

run_summary = pipeline_result["run_summary"]
job_results = pipeline_result["jobs"]

assert run_summary["jobs_discovered"] == 1
assert run_summary["jobs_sent_to_llm"] == 1
assert run_summary["jobs_skipped_before_llm"] == 0
assert len(job_results) == 1

result_job = job_results[0]

assert result_job.get("source_url") == eligible_job.get("source_url"), (
    "The pipeline result does not preserve source_url."
)

assert result_job.get("skipped_before_llm") is not True, (
    "The eligible job was unexpectedly skipped before LLM review."
)

assert result_job.get("final_recommendation") in {
    "apply",
    "review",
    "skip",
}, (
    "The Job Analysis Agent returned an invalid recommendation."
)


print("\n" + "=" * 60)
print("Phase 3–5 Live Eligible-Job Pipeline Results")
print("=" * 60)

print(
    f"Live jobs inspected   : "
    f"{len(job_data_list)}"
)
print(
    f"Selected job          : "
    f"{eligible_job.get('title')}"
)
print(
    f"Institution           : "
    f"{eligible_job.get('company')}"
)
print(
    f"Jobs discovered       : "
    f"{run_summary['jobs_discovered']}"
)
print(
    f"Jobs sent to LLM      : "
    f"{run_summary['jobs_sent_to_llm']}"
)
print(
    f"Skipped before LLM    : "
    f"{run_summary['jobs_skipped_before_llm']}"
)
print(
    f"LLM utilization       : "
    f"{run_summary['llm_utilization_percent']:.1f}%"
)
print(
    f"Elapsed time          : "
    f"{run_summary['elapsed_time_sec']:.2f} sec"
)

print("\nAnalyzed job record:")

print(
    json.dumps(
        result_job,
        indent=4,
    )
)

print(
    "\nLive HigherEdJobs pass-to-LLM pipeline passed."
)
