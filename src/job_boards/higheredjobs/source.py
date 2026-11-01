"""
Phase 3 - HigherEdJobs Source
Coordinates live alert pagination, posting retrieval, and parsing.
"""

from src.config.job_boards import HIGHEREDJOBS
from src.job_boards.higheredjobs.client import HigherEdJobsClient
from src.job_boards.higheredjobs.reader import HigherEdJobsReader


class HigherEdJobsSource:
    """
    Produces normalized job records from a live HigherEdJobs alert.
    """

    def __init__(
        self,
        landing_url=None,
        remote_alert=False,
        client: HigherEdJobsClient | None = None,
        reader: HigherEdJobsReader | None = None
    ):
        if client is None and not landing_url:
            raise ValueError("HigherEdJobsSource requires a landing URL.")
        self.client = client or HigherEdJobsClient(landing_url=landing_url)
        self.reader = reader or HigherEdJobsReader()
        self.remote_alert = remote_alert

    def load_jobs(self, limit: int | None = None) -> list[dict]:
        """
        Retrieve and parse jobs from the configured alert.

        Args:
            limit:
                Optional maximum number of postings to process.
                When omitted, all extracted postings are processed.

        Returns:
            A list of normalized job records.
        """

        self.client.connect_browser()

        try:
            return self._load_jobs_from_connected_browser(limit)
        finally:
            self.client.close()

    def _load_jobs_from_connected_browser(
        self,
        limit: int | None,
    ) -> list[dict]:
        """Retrieve jobs while the client owns an active CDP connection."""

        results_page = self.client.open_landing_page()

        results_page.wait_for_selector(
            HIGHEREDJOBS["job_link_selector"],
            timeout=self.client.request_timeout * 1000
        )

        results_page_html = results_page.content()
        current_page_number = 1
        job_links = []
        seen_job_links = set()

        # HigherEdJobs exposes only the fixed-size current page in the DOM.
        # Collect and deduplicate links before opening individual postings,
        # because job navigation replaces the current results page.
        while True:
            page_job_links = self.client.extract_job_links(
                results_page_html
            )

            for job_url in page_job_links:
                if job_url not in seen_job_links:
                    seen_job_links.add(job_url)
                    job_links.append(job_url)

            if limit is not None and len(job_links) >= limit:
                job_links = job_links[:limit]
                break

            next_page_number = (
                self.client.get_next_alert_result_page_number(
                    results_page_html,
                    current_page_number,
                )
            )
            if next_page_number is None:
                break

            results_page_html = self.client.get_alert_result_page(
                next_page_number
            )
            current_page_number = next_page_number

        job_records = []

        for job_url in job_links:
            try:
                job_html = self.client.get_job_page(job_url)

                job_data = self.reader.from_html(
                    job_html,
                    source_url=job_url
                )

            except Exception as error:
                job_data = {
                    "source_type": "higheredjobs_live",
                    "source_url": job_url,
                    "manual_review_required": True,
                    "review_reason": (
                        "Unable to retrieve or parse the posting: "
                        f"{error}"
                    ),
                    "remote?": "Yes" if self.remote_alert else "No",
                }

            if self.remote_alert:
                job_data["remote?"] = "Yes"
            else:
                job_data["remote?"] = (
                    "Yes" if job_data.get("remote?") == "Yes" else "No"
                )

            job_records.append(job_data)

        return job_records
