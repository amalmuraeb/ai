"""
Phase 3 - HigherEdJobs Pagination Test
Validates multi-page discovery, deduplication, limits, and cleanup.
"""

from src.config.job_boards import HIGHEREDJOBS
from src.job_boards.higheredjobs.client import HigherEdJobsClient
from src.job_boards.higheredjobs.source import HigherEdJobsSource
from src.job_boards.higheredjobs.reader import HigherEdJobsReader


def _results_html(job_codes, next_page=None):
    job_links = "".join(
        (
            '<a href="details.cfm?JobCode='
            f'{job_code}&Title=Test%20Job%20{job_code}">Job</a>'
        )
        for job_code in job_codes
    )
    pagination = (
        '<a href="viewagent.cfm?AgentID=1&Page='
        f'{next_page}">{next_page}</a>'
        if next_page is not None
        else ""
    )
    return f"<html><body>{job_links}{pagination}</body></html>"


class FakePage:
    def __init__(self, html):
        self.html = html

    def wait_for_selector(self, selector, timeout):
        return None

    def content(self):
        return self.html


class FakeClient:
    def __init__(self):
        jobs_per_page = HIGHEREDJOBS["JOB_POSTS_PER_PAGE"]
        self.request_timeout = 30
        self.page_parser = HigherEdJobsClient()
        self.pages = {
            1: _results_html(
                range(1, jobs_per_page + 1),
                next_page=2,
            ),
            # Repeat one link to verify cross-page deduplication.
            2: _results_html(
                range(jobs_per_page, 2 * jobs_per_page),
                next_page=3,
            ),
            3: _results_html(
                range(2 * jobs_per_page, 2 * jobs_per_page + 4)
            ),
        }
        self.requested_result_pages = []
        self.closed = False

    def connect_browser(self):
        return None

    def open_landing_page(self):
        return FakePage(self.pages[1])

    def extract_job_links(self, html):
        return self.page_parser.extract_job_links(html)

    def get_next_alert_result_page_number(self, html, current_page):
        return self.page_parser.get_next_alert_result_page_number(
            html,
            current_page,
        )

    def get_alert_result_page(self, page_number):
        self.requested_result_pages.append(page_number)
        return self.pages[page_number]

    def get_job_page(self, job_url):
        return job_url

    def close(self):
        self.closed = True


class FakeReader:
    def from_html(self, html, source_url=None):
        return {
            "title": "Test job",
            "company": "Test university",
            "source_url": source_url,
        }


class FailingClient(FakeClient):
    def open_landing_page(self):
        raise RuntimeError("Simulated results-page failure.")


def main():
    application_posting = HigherEdJobsReader().from_html(
        """
        <h1 id="jobtitle-header">Professor of Engineering</h1>
        <a id="js-applyurl"
           href="/clickthru/redirect.cfm?JobCode=123"
           data-orig-href="https://jobs.example.edu/postings/123">
          Apply Now
        </a>
        """,
        source_url=(
            "https://www.higheredjobs.com/details.cfm?JobCode=123"
        ),
    )
    assert application_posting["apply_url"] == (
        "https://jobs.example.edu/postings/123"
    )

    redirect_posting = HigherEdJobsReader().from_html(
        """
        <h1 id="jobtitle-header">Professor of Engineering</h1>
        <a id="js-applyurl" href="/clickthru/redirect.cfm?JobCode=456">
          Apply Now
        </a>
        """,
        source_url=(
            "https://www.higheredjobs.com/details.cfm?JobCode=456"
        ),
    )
    assert redirect_posting["apply_url"] == (
        "https://www.higheredjobs.com/clickthru/redirect.cfm?JobCode=456"
    )

    remote_posting = HigherEdJobsReader().from_html(
        """
        <script type="application/ld+json">
        {
          "@type": "JobPosting",
          "title": "Faculty, Technology (Remote)",
          "hiringOrganization": {"name": "Purdue Global"},
          "jobLocationType": "TELECOMMUTE",
          "description": "Teach technology courses."
        }
        </script>
        """
    )
    assert remote_posting["remote?"] == "Yes"
    assert remote_posting["apply_url"] is None

    jobs_per_page = HIGHEREDJOBS["JOB_POSTS_PER_PAGE"]
    client = FakeClient()
    source = HigherEdJobsSource(client=client, reader=FakeReader())

    jobs = source.load_jobs()
    expected_unique_jobs = 2 * jobs_per_page + 3
    assert len(jobs) == expected_unique_jobs
    assert len({job["source_url"] for job in jobs}) == expected_unique_jobs
    assert client.requested_result_pages == [2, 3]
    assert client.closed is True

    limited_client = FakeClient()
    limited_source = HigherEdJobsSource(
        client=limited_client,
        reader=FakeReader(),
    )
    limited_job_count = jobs_per_page + 5
    limited_jobs = limited_source.load_jobs(limit=limited_job_count)
    assert len(limited_jobs) == limited_job_count
    assert limited_client.requested_result_pages == [2]
    assert limited_client.closed is True

    remote_client = FakeClient()
    remote_source = HigherEdJobsSource(
        client=remote_client,
        reader=FakeReader(),
        remote_alert=True,
    )
    remote_jobs = remote_source.load_jobs(limit=1)
    assert remote_jobs[0]["remote?"] == "Yes"
    assert remote_client.closed is True

    failing_client = FailingClient()
    failing_source = HigherEdJobsSource(
        client=failing_client,
        reader=FakeReader(),
    )
    try:
        failing_source.load_jobs()
    except RuntimeError as error:
        assert str(error) == "Simulated results-page failure."
    else:
        raise AssertionError("Expected simulated results-page failure.")
    assert failing_client.closed is True

    print("HigherEdJobs pagination regression test passed.")


if __name__ == "__main__":
    main()
