"""
Phase 3 - HigherEdJobs Page Retrieval Test
Validates retrieval of one live job posting through CDP.
"""

import argparse

from src.config.job_boards import HIGHEREDJOBS
from src.job_boards.higheredjobs.client import HigherEdJobsClient

parser = argparse.ArgumentParser()
parser.add_argument("--landing_url", required=True)
arguments = parser.parse_args()

client = HigherEdJobsClient(landing_url=arguments.landing_url)
client.connect_browser()

results_page = client.open_landing_page()
results_page.wait_for_timeout(HIGHEREDJOBS["page_stabilization_delay_ms"])

job_links = client.extract_job_links(results_page.content())

if not job_links:
    raise RuntimeError("No HigherEdJobs posting links were extracted.")

job_url = job_links[0]
job_html = client.get_job_page(job_url)

print(f"Requested URL: {job_url}")
print(f"Current URL: {client.page.url}")
print(f"Title: {client.page.title()}")
print(f"HTML characters: {len(job_html)}")

assert client.page.url.startswith("https://www.higheredjobs.com/")
assert len(job_html) > 0

print("Live HigherEdJobs posting retrieval passed.")
