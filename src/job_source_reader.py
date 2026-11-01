"""
Phase 3 - Job Source Reader
Converts raw job posting text into structured job data for downstream analysis.
"""

from pydoc import html
import re
from bs4 import BeautifulSoup

from src.config.job_source_reader import JOB_SOURCE_READER

class JobSourceReader:
    def from_text(self, job_text):
        company = None
        title = None
        city = None
        state = None
        salary = None
        employment_type = None
        posting_date = None
        closing_date = None
        remote = "No"

        posting_date_match = re.search(r"Posting Date:\s*(.*)", job_text)
        if posting_date_match:
            posting_date = posting_date_match.group(1).strip()

        closing_date_match = re.search(r"Closing Date:\s*(.*)", job_text)
        if closing_date_match:
            closing_date = closing_date_match.group(1).strip()

        company_match = re.search(r"Company:\s*(.*)", job_text)
        if company_match:
            company = company_match.group(1).strip()

        title_match = re.search(r"Position:\s*(.*)", job_text)
        if title_match:
            title = title_match.group(1).strip()

        location_match = re.search(r"Location:\s*(.*)", job_text)
        if location_match:
            location = location_match.group(1).strip()

            if "online/remote" in location.casefold() or re.search(
                r"\bremote\b",
                location,
                flags=re.IGNORECASE,
            ):
                remote = "Yes"

            if "," in location:
                parts = location.split(",", 1)
                city = parts[0].strip()
                state = parts[1].strip()
            else:
                city = location

        salary_match = re.search(r"Salary:\s*(.*)", job_text)
        if salary_match:
            salary = salary_match.group(1).strip()

        full_time_marker = JOB_SOURCE_READER["full_time_marker"]

        if full_time_marker in job_text.lower():
            employment_type = full_time_marker

        return {
            "source_type": "manual_text",
            "company": company,
            "title": title,
            "city": city,
            "state": state,
            "salary": salary,
            "employment_type": employment_type,
            "posting_date": posting_date,
            "closing_date": closing_date,
            "remote?": remote,
            "raw_text": job_text
        }

    def from_html(self, html):
        """
        Convert an HTML job posting into structured job data.
        Extracts the visible text from the HTML page and reuses the
        existing from_text() parser.
        """

        soup = BeautifulSoup(html, "html.parser")

        visible_text = soup.get_text("\n", strip=True)

        return self.from_text(visible_text)

    def to_analysis_text(self, job_data):
        return f"""
        Posting Date: {job_data.get('posting_date')}

        Closing Date: {job_data.get('closing_date')}

        Company: {job_data.get('company')}

        Position: {job_data.get('title')}

        Location: {job_data.get('city')}, {job_data.get('state')}

        Remote: {job_data.get('remote?', 'No')}

        Employment Type: {job_data.get('employment_type')}

        Employment Type Match: {job_data.get('employment_type_match')}

        Salary: {job_data.get('salary')}

        Salary Minimum: {job_data.get('salary_min')}

        Salary Maximum: {job_data.get('salary_max')}

        Salary Match: {job_data.get('salary_match')}

        Is Closing Date Soon: {job_data.get('is_closing_date_soon')}

        Provisioner Warnings: {job_data.get('provisioner_warnings', [])}

        Raw Job Posting:
        {job_data.get('raw_text')}
        """.strip()
