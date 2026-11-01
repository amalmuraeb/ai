"""
Phase 3 - HigherEdJobs Reader
Parses HigherEdJobs metadata and visible HTML into normalized jobs.
"""

import html
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from src.config.job_boards import HIGHEREDJOBS
from src.job_source_reader import JobSourceReader
from src.config.page_security_check import SECURITY_CHECK_MARKERS


class HigherEdJobsReader(JobSourceReader):

    @staticmethod
    def _apply_url(soup, source_url: str | None = None) -> str | None:
        """Return the employer's application URL from the posting page."""
        apply_link = soup.select_one("a#js-applyurl")
        if apply_link is None:
            apply_link = next(
                (
                    link
                    for link in soup.find_all("a", href=True)
                    if "apply now" in link.get_text(" ", strip=True).casefold()
                ),
                None,
            )
        if apply_link is None:
            return None

        candidate = (
            apply_link.get("data-orig-href")
            or apply_link.get("href")
            or ""
        ).strip()
        if not candidate:
            return None

        source_scheme = urlparse(source_url or "").scheme.casefold()
        base_url = (
            source_url
            if source_scheme in {"http", "https"}
            else HIGHEREDJOBS["base_url"] + "/"
        )
        resolved = urljoin(base_url, candidate)
        if urlparse(resolved).scheme.casefold() not in {"http", "https"}:
            return None
        return resolved

    @staticmethod
    def _remote_value(*values) -> str:
        """Return Yes when source-authoritative text identifies remote work."""
        text = " ".join(str(value or "") for value in values).casefold()
        return (
            "Yes"
            if any(
                marker in text
                for marker in HIGHEREDJOBS["remote_markers"]
            )
            else "No"
        )

    def from_html(self, html_content: str, source_url: str | None = None) -> dict:
        soup = BeautifulSoup(html_content, "html.parser")

        job_data = self._detect_page_status(soup)

        if job_data is None:
            job_data = self._parse_jsonld(html_content)

        if job_data is None:
            job_data = self._parse_html(html_content)

        if source_url:
            job_data["source_url"] = source_url
        job_data["apply_url"] = self._apply_url(soup, source_url)

        job_data["remote?"] = (
            "Yes"
            if job_data.get("remote?") == "Yes"
            or self._remote_value(
                job_data.get("title"),
                job_data.get("city"),
                job_data.get("state"),
                job_data.get("raw_text"),
            ) == "Yes"
            else "No"
        )

        return job_data

    def _parse_jsonld(self, html_content: str) -> dict | None:
        soup = BeautifulSoup(html_content, "html.parser")

        for script in soup.find_all(
            "script",
            type="application/ld+json"
        ):
            script_text = script.string or ""

            try:
                data = json.loads(script_text)
            except json.JSONDecodeError:
                cleaned_script = re.sub(
                    r",\s*([}\]])",
                    r"\1",
                    script_text
                )

                try:
                    data = json.loads(cleaned_script)
                except json.JSONDecodeError:
                    continue

            if data.get("@type") != "JobPosting":
                continue

            organization = data.get("hiringOrganization", {})
            location = data.get("jobLocation", {})
            address = location.get("address", {})

            title = html.unescape(
                html.unescape(data.get("title", ""))
            )

            description_html = data.get("description", "")
            description_text = BeautifulSoup(
                html.unescape(description_html),
                "html.parser"
            ).get_text("\n", strip=True)

            employment_type = data.get("employmentType")

            if employment_type == "FULL_TIME":
                employment_type = "full-time"

            remote = self._remote_value(
                data.get("jobLocationType"),
                title,
                address.get("addressLocality"),
                address.get("addressRegion"),
                description_text,
            )
            if str(data.get("jobLocationType") or "").upper() == (
                "TELECOMMUTE"
            ):
                remote = "Yes"

            return {
                "source_type": "higheredjobs_html",
                "company": organization.get("name"),
                "title": title,
                "city": address.get("addressLocality"),
                "state": address.get("addressRegion"),
                "country": address.get("addressCountry"),
                "salary": self._extract_base_salary(data),
                "employment_type": employment_type,
                "posting_date": data.get("datePosted"),
                "closing_date": data.get("validThrough"),
                "remote?": remote,
                "raw_text": description_text
            }

        return None

    def _parse_html(self, html_content: str) -> dict:
        soup = BeautifulSoup(html_content, "html.parser")

        selectors = HIGHEREDJOBS["selectors"]

        title_element = soup.select_one(selectors["title"])
        company_element = soup.select_one(selectors["company"])
        location_element = soup.select_one(selectors["location"])
        job_info_element = soup.select_one(selectors["job_info"])
        description_element = soup.select_one(selectors["description"])

        title = (
            title_element.get_text(" ", strip=True)
            if title_element
            else None
        )

        company = (
            company_element.get_text(" ", strip=True)
            if company_element
            else None
        )

        city = None
        state = None
        location_text = ""

        if location_element:
            location_text = location_element.get_text(" ", strip=True)

            if location_text.lower().startswith("in "):
                location_text = location_text[3:].strip()

            if "," in location_text:
                city, state = [
                    part.strip()
                    for part in location_text.rsplit(",", 1)
                ]

        job_info = (
            job_info_element.get_text("\n", strip=True)
            if job_info_element
            else ""
        )

        employment_type = None

        if "full-time" in job_info.lower():
            employment_type = "full-time"
        elif "part-time" in job_info.lower():
            employment_type = "part-time"

        raw_text = ""

        if description_element:
            raw_text = description_element.get_text(
                "\n",
                strip=True
            )

        if not raw_text:
            raw_text = soup.get_text(
                "\n",
                strip=True
            )

        if not title and not raw_text:
            raise ValueError(
                "Unable to extract job data from HigherEdJobs HTML."
            )

        return {
            "source_type": "higheredjobs_html_fallback",
            "company": company,
            "title": title,
            "city": city,
            "state": state,
            "country": HIGHEREDJOBS["default_country"],
            "salary": None,
            "employment_type": employment_type,
            "posting_date": None,
            "closing_date": None,
            "remote?": self._remote_value(
                title,
                location_text,
                raw_text,
            ),
            "raw_text": raw_text
        }

    def _extract_base_salary(self, data: dict):
        base_salary = data.get("baseSalary")

        if not isinstance(base_salary, dict):
            return None

        value = base_salary.get("value")

        if isinstance(value, dict):
            return value.get("value")

        return value

    def _detect_page_status(self, soup: BeautifulSoup) -> dict | None:

        normalized_text = soup.get_text(" ", strip=True).casefold()

        if any(marker in normalized_text for marker in SECURITY_CHECK_MARKERS):
            return {
                "title": None,
                "company": None,
                "page_status": "captcha_required",
                "manual_review_required": True,
                "review_reason": (
                    "HigherEdJobs requires an additional security "
                    "check before the posting content can be viewed."
                )
            }

        if (
            "this position is no longer an active posting" in normalized_text
            or "position deleted" in normalized_text
        ):
            return {
                "title": None,
                "company": None,
                "page_status": "deleted",
                "manual_review_required": True,
                "review_reason": (
                    "The HigherEdJobs posting is deleted "
                    "or no longer active."
                )
            }

        if "sign in" in normalized_text and "job detail" not in normalized_text:
            return {
                "title": None,
                "company": None,
                "page_status": "login_required",
                "manual_review_required": True,
                "review_reason": (
                    "HigherEdJobs requires login before "
                    "the posting can be viewed."
                )
            }

        return None
