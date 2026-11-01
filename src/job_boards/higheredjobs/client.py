"""
Phase 3 - HigherEdJobs Client
Connects through CDP and retrieves result and posting pages.
"""

from playwright.sync_api import sync_playwright
from src.config.job_boards import HIGHEREDJOBS
from src.config.browser import BROWSER
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup

class HigherEdJobsClient:
    """
    Handles communication with HigherEdJobs.
    """

    def __init__(self, landing_url=None):
        self.base_url = HIGHEREDJOBS["base_url"]
        self.landing_url = landing_url
        self.cdp_url = BROWSER["cdp_url"]
        self.request_timeout = HIGHEREDJOBS["request_timeout"]
        self.max_retries = HIGHEREDJOBS["max_retries"]
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def get_alert_result_page(self, page_number):
        """
        Return the HTML of one alert-results page.
        """

        if self.page is None:
            raise RuntimeError("Browser is not connected.")
        if not self.landing_url:
            raise RuntimeError("No HigherEdJobs landing URL was supplied.")
        if page_number < 1:
            raise ValueError("Results page number must be at least 1.")

        parsed_url = urlparse(self.landing_url)
        query = parse_qs(parsed_url.query)
        query["Page"] = [str(page_number)]
        page_url = urlunparse(
            parsed_url._replace(query=urlencode(query, doseq=True))
        )

        self.page.goto(
            page_url,
            wait_until=HIGHEREDJOBS["navigation_wait_until"],
        )

        if self.is_login_required():
            raise RuntimeError(
                "HigherEdJobs login is required. Sign in through the "
                "connected browser and rerun."
            )

        self.page.wait_for_selector(
            HIGHEREDJOBS["job_link_selector"],
            timeout=self.request_timeout * 1000,
        )

        return self.page.content()

    def get_next_alert_result_page_number(
        self,
        results_page_html,
        current_page_number,
    ):
        """Return the next linked results-page number, when present."""
        soup = BeautifulSoup(results_page_html, "html.parser")
        expected_page_number = current_page_number + 1

        for link in soup.find_all("a", href=True):
            parsed_url = urlparse(link["href"].strip())
            query = {
                key.casefold(): values
                for key, values in parse_qs(parsed_url.query).items()
            }
            page_values = query.get("page", [])

            if any(
                value.isdigit()
                and int(value) == expected_page_number
                for value in page_values
            ):
                return expected_page_number

        return None

    def get_job_page(self, job_url):
        """
        Open one job posting and return its HTML.
        """

        if self.page is None:
            raise RuntimeError("Browser is not connected.")

        if job_url.startswith("/"):
            job_url = f"{self.base_url}{job_url}"

        self.page.goto(
            job_url,
            wait_until=HIGHEREDJOBS["navigation_wait_until"]
        )

        return self.page.content()

    def extract_job_links(self, results_page_html):
        """
        Return unique job-posting URLs from one alert-results page.
        """

        soup = BeautifulSoup(results_page_html, "html.parser")
        job_links = []
        seen = set()

        for link in soup.find_all("a", href=True):
            href = link["href"].strip()

            if not href.lower().startswith(
                HIGHEREDJOBS["job_link_href_prefix"]
            ):
                continue

            job_url = urljoin(self.base_url, href)

            if job_url not in seen:
                seen.add(job_url)
                job_links.append(job_url)

        return job_links

    def connect_browser(self):
        """
        Connect to the configured browser through CDP.
        """

        self.playwright = sync_playwright().start()

        try:
            self.browser = self.playwright.chromium.connect_over_cdp(
                self.cdp_url
            )

            if not self.browser.contexts:
                raise RuntimeError("No browser context is available.")

            self.context = self.browser.contexts[0]

            self.page = (
                self.context.pages[0]
                if self.context.pages
                else self.context.new_page()
            )

            self.page.bring_to_front()

            return self.page
        except Exception:
            self.close()
            raise

    def close(self):
        """Stop Playwright without closing the externally managed Edge."""

        if self.playwright is None:
            return

        try:
            # Do not call browser.close(): Edge was launched and is owned by
            # the user. Stopping Playwright closes only this client/driver.
            self.playwright.stop()
        finally:
            self.page = None
            self.context = None
            self.browser = None
            self.playwright = None

    def open_landing_page(self):
        if self.page is None:
            raise RuntimeError("Browser is not connected.")
        if not self.landing_url:
            raise RuntimeError("No HigherEdJobs landing URL was supplied.")

        self.page.goto(
            self.landing_url,
            wait_until=HIGHEREDJOBS["navigation_wait_until"]
        )

        if self.is_login_required():
            raise RuntimeError("HigherEdJobs login is required. Sign in through the connected browser and rerun.")

        return self.page

    def is_login_required(self):
        """
        Return True when HigherEdJobs redirects to a login page.
        """

        if self.page is None:
            raise RuntimeError("Browser is not connected.")

        return "/Login/" in self.page.url or "Timeout=Session" in self.page.url
