"""
Phase 6 - HigherEdJobs Document Source
Retrieves current apply-job posting bodies for document planning.
"""

from src.job_boards.higheredjobs.client import HigherEdJobsClient
from src.job_boards.higheredjobs.reader import HigherEdJobsReader


class HigherEdJobsDocumentSource:
    """Retrieve current posting bodies for analyzed ``apply`` jobs."""

    def __init__(self, client=None, reader=None):
        self.client = client or HigherEdJobsClient()
        self.reader = reader or HigherEdJobsReader()

    def load_postings(self, jobs):
        jobs = list(jobs)
        if not jobs:
            return []

        posting_results = []
        self.client.connect_browser()

        try:
            for job in jobs:
                source_url = job.get("source_url")

                try:
                    if not source_url:
                        raise ValueError("Apply job has no source_url.")

                    html = self.client.get_job_page(source_url)
                    parsed = self.reader.from_html(
                        html,
                        source_url=source_url,
                    )
                    posting_text = parsed.get("raw_text")

                    if not posting_text:
                        reason = parsed.get(
                            "review_reason",
                            "Posting body is unavailable.",
                        )
                        raise ValueError(reason)

                    posting_results.append(
                        {
                            "job": job,
                            "posting_text": posting_text,
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
        finally:
            self.client.close()

        return posting_results
