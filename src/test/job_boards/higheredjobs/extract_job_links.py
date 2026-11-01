"""
Phase 3 - HigherEdJobs Link Extraction Test
Validates live result-count and unique posting-link extraction.
"""

import argparse
import re

from src.config.job_boards import HIGHEREDJOBS
from src.job_boards.higheredjobs.client import HigherEdJobsClient

parser = argparse.ArgumentParser()
parser.add_argument("--landing_url", required=True)
arguments = parser.parse_args()

client = HigherEdJobsClient(landing_url=arguments.landing_url)
client.connect_browser()
page = client.open_landing_page()
page.wait_for_timeout(HIGHEREDJOBS["page_stabilization_delay_ms"])

page_text = page.locator("body").inner_text()
total_match = re.search(r"Results\s+\d+\s*-\s*\d+\s+of\s+([\d,]+)", page_text)

if not total_match:
    raise RuntimeError("Unable to determine the total HigherEdJobs result count.")

expected_total = int(total_match.group(1).replace(",", ""))
job_links = client.extract_job_links(page.content())

print(f"Expected jobs: {expected_total}")
print(f"Extracted jobs: {len(job_links)}")

assert len(job_links) == expected_total, f"Expected {expected_total} unique job links, but extracted {len(job_links)}."

print("Complete HigherEdJobs alert link extraction passed.")
