"""
Phase 3 - Live HigherEdJobs Reader Test
Validates live posting parsing and source-URL preservation.
"""

import argparse
import json

from src.config.job_boards import HIGHEREDJOBS
from src.job_boards.higheredjobs.client import HigherEdJobsClient
from src.job_boards.higheredjobs.reader import HigherEdJobsReader


parser = argparse.ArgumentParser()
parser.add_argument("--landing_url", required=True)
arguments = parser.parse_args()

client = HigherEdJobsClient(landing_url=arguments.landing_url)
reader = HigherEdJobsReader()

client.connect_browser()

results_page = client.open_landing_page()
results_page.wait_for_timeout(HIGHEREDJOBS["page_stabilization_delay_ms"])

job_links = client.extract_job_links(results_page.content())

if not job_links:
    raise RuntimeError("No HigherEdJobs posting links were extracted.")

job_url = job_links[0]
job_html = client.get_job_page(job_url)

job_data = reader.from_html(
    job_html,
    source_url=job_url
)

print(json.dumps(job_data, indent=4))

assert job_data.get("source_url") == job_url
assert job_data.get("title") or job_data.get("manual_review_required")
assert job_data.get("raw_text") or job_data.get("manual_review_required")

print("Live HigherEdJobs retrieval and parsing passed.")
