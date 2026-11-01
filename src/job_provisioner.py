"""
Phase 4 - Job Provisioner
Applies deterministic filtering before LLM analysis.
"""

import re
from datetime import date, datetime
from src.config.job_provisioner import (
    DATE_FORMATS,
    EXCLUDED_FOCUS_AREA_RULES,
    MILITARY_CONTEXT,
    MILITARY_IGNORE_CONTEXT,
    RELIGIOUS_INSTITUTION_NAME_PATTERNS,
    RELIGIOUS_MISSION_PATTERNS,
    SALARY_VALUE_PATTERN,
    EXCLUDED_ROLES_PATTERNS,
    POSTING_AGE_MAX_YEARS,
    POSTING_AGE_REVIEW_YEARS,
)

class JobProvisioner:

    def __init__(self, user_profile):
        self.user_profile = user_profile

    def _parse_salary(self, salary_text):
        """
        Convert salary text into minimum and maximum annual values.

        Examples:
        "$115,000 - $125,000" -> (115000, 125000)
        "$160,000"            -> (160000, 160000)
        """

        if not salary_text:
            return None, None

        salary_values = re.findall(SALARY_VALUE_PATTERN, salary_text)

        if not salary_values:
            return None, None

        normalized_values = [
            int(value.replace(",", ""))
            for value in salary_values
        ]

        return min(normalized_values), max(normalized_values)

    def _parse_date(self, date_text):
        """
        Convert common job-posting date formats into a date object.

        Supported examples:
        "2026-11-10"
        "November 10, 2026"
        "Nov 10, 2026"
        "11/10/2026"
        """

        if not date_text:
            return None

        normalized = str(date_text).strip()
        try:
            return datetime.fromisoformat(
                normalized.replace("Z", "+00:00")
            ).date()
        except ValueError:
            pass

        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(
                    normalized,
                    date_format
                ).date()
            except ValueError:
                continue

        return None

    @staticmethod
    def _anniversary(original_date, years):
        """Return a calendar-year anniversary, including leap-day inputs."""
        try:
            return original_date.replace(year=original_date.year + years)
        except ValueError:
            return original_date.replace(
                year=original_date.year + years,
                day=28,
            )

    def should_discard_stale_posting(self, job_data, run_date=None):
        """Return True when posting age makes a listing unactionable.

        Jobs older than two years are always stale. Jobs between one and two
        years old remain eligible only with a parseable closing date outside
        the configured closing-soon window. Missing posting dates are retained.
        """
        run_date = run_date or date.today()
        posting_date = self._parse_date(job_data.get("posting_date"))
        if posting_date is None:
            return False

        review_date = self._anniversary(
            posting_date,
            POSTING_AGE_REVIEW_YEARS,
        )
        maximum_date = self._anniversary(
            posting_date,
            POSTING_AGE_MAX_YEARS,
        )
        if run_date >= maximum_date:
            return True
        if run_date <= review_date:
            return False

        closing_date = self._parse_date(job_data.get("closing_date"))
        return (
            closing_date is None
            or self._is_closing_date_soon(closing_date, run_date)
        )

    def _is_closing_date_soon(self, closing_date, run_date=None):
        """
        Return True when the closing month is less than the configured
        number of months from the current run month.

        Missing or unrecognized dates return False.
        """

        if closing_date is None:
            return False

        if run_date is None:
            run_date = date.today()

        threshold_months = self.user_profile[
            "application_constraints"
        ]["closing_date_soon_threshold_months"]

        months_until_closing = (
            (closing_date.year - run_date.year) * 12
            + closing_date.month
            - run_date.month
        )

        return months_until_closing < threshold_months

    def evaluate(self, job_data):
        reasons = []
        warnings = []

        raw_text = job_data.get("raw_text", "").lower()
        employment_type = job_data.get("employment_type")
        salary_text = job_data.get("salary")
        allowed_employment_types = self.user_profile["employment_type"]["allowed_types"]

        employment_type_match = (
            employment_type is not None
            and employment_type.lower() in
            [t.lower() for t in allowed_employment_types]
        )

        salary_min, salary_max = self._parse_salary(salary_text)
        minimum_required_salary = self.user_profile["salary_constraint"]["minimum_salary_usd"]

        if salary_max is None:
            salary_match = None
        else:
            salary_match = salary_max >= minimum_required_salary

        closing_date = self._parse_date(
            job_data.get("closing_date")
        )

        is_closing_date_soon = self._is_closing_date_soon(
            closing_date
        )

        minimum_required_salary = self.user_profile[
            "salary_constraint"
        ]["minimum_salary_usd"]

        if not employment_type_match:
            reasons.append(
                f"Employment type is not allowed: {employment_type}"
        )

        excluded_role = self._find_excluded_role(job_data)
        if excluded_role:
                reasons.append(f"Excluded role: {excluded_role}")

        excluded_institution = self._find_excluded_institution(job_data)
        if excluded_institution:
            reasons.append(
                f"Excluded institution: {excluded_institution}"
            )

        excluded_focus_area = self._find_excluded_focus_area(job_data)
        if excluded_focus_area:
            reasons.append(
                f"Excluded focus area: {excluded_focus_area}"
            )
        passed_provisioner = len(reasons) == 0

        #
        # Remove common HR/legal phrases before checking for
        # military/defense context.
        #
        filtered_text = raw_text

        for phrase in MILITARY_IGNORE_CONTEXT:
            filtered_text = filtered_text.replace(
                phrase.lower(),
                ""
            )

        #
        # Reject only if a strong military/defense indicator remains.
        #
        excluded_industries = {
            value.casefold()
            for value in self.user_profile["exclude_industries"]
        }
        if any(
            "military" in value or "defense" in value
            for value in excluded_industries
        ):
            for phrase in MILITARY_CONTEXT:
                if phrase.lower() in filtered_text:
                    reasons.append(
                        "Excluded industry: Military/Defense"
                    )
                    break

        if salary_max is not None:
            if salary_max < minimum_required_salary:
                reasons.append(
                    f"Maximum salary ${salary_max:,} is below "
                    f"the required minimum of "
                    f"${minimum_required_salary:,}"
                )

            elif salary_min < minimum_required_salary <= salary_max:
                warnings.append(
                    f"Salary range begins below the required minimum "
                    f"of ${minimum_required_salary:,}"
                )

        skip_if_closing_soon = self.user_profile[
            "application_constraints"
        ]["skip_if_closing_date_soon"]

        if is_closing_date_soon and skip_if_closing_soon:
            threshold_months = self.user_profile[
                "application_constraints"
            ]["closing_date_soon_threshold_months"]

            reasons.append(
                f"Closing date is less than "
                f"{threshold_months} months away"
            )

        provisioned_job = {
            **job_data,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_match": salary_match,
            "employment_type_match": employment_type_match,
            "is_closing_date_soon": is_closing_date_soon,
            "provisioner_warnings": warnings
        }

        return {
            "passed_provisioner": len(reasons) == 0,
            "reasons": reasons,
            "warnings": warnings,
            "job_data": provisioned_job
        }

    def create_skip_record(self, job_data, reasons):
        """
        Create an audit record for a job rejected before LLM analysis.
        """

        return {
            "title": job_data.get("title"),
            "company": job_data.get("company"),
            "city": job_data.get("city"),
            "state": job_data.get("state"),
            "source_url": job_data.get("source_url"),
            "remote?": job_data.get("remote?", "No"),
            "posting_date": job_data.get("posting_date"),
            "closing_date": job_data.get("closing_date"),
            "salary": job_data.get("salary"),
            "salary_min": job_data.get("salary_min"),
            "salary_max": job_data.get("salary_max"),
            "is_closing_date_soon": job_data.get(
                "is_closing_date_soon",
                False,
            ),
            "final_recommendation": "skip",
            "skipped_before_llm": True,
            "skip_reasons": list(reasons),
        }

    def _find_excluded_role(self, job_data):
        """
        Return the excluded-role category matching the job title.

        Returns None when no excluded role is detected.
        """

        title = str(job_data.get("title") or "").strip()

        if not title:
            return None

        selected_roles = set(self.user_profile["exclude_roles"])
        for role_category, patterns in EXCLUDED_ROLES_PATTERNS.items():
            if role_category not in selected_roles:
                continue
            for pattern in patterns:
                if re.search(pattern, title, flags=re.IGNORECASE):
                    return role_category

        return None

    def _find_excluded_institution(self, job_data):
        """Return the religious-orientation exclusion when detected.

        Institution names and mission language are checked separately so
        ordinary equal-opportunity references to religion do not reject a
        posting from an otherwise secular institution.
        """

        company = str(job_data.get("company") or "").strip()
        raw_text = str(job_data.get("raw_text") or "").strip()

        if "Religious mission or affiliation" not in set(
            self.user_profile["exclude_institution_orientations"]
        ):
            return None

        for pattern in RELIGIOUS_INSTITUTION_NAME_PATTERNS:
            if re.search(pattern, company, flags=re.IGNORECASE):
                return "Religious mission or affiliation"

        for pattern in RELIGIOUS_MISSION_PATTERNS:
            if re.search(pattern, raw_text, flags=re.IGNORECASE):
                return "Religious mission or affiliation"

        return None

    def _find_excluded_focus_area(self, job_data):
        """Return a dominant excluded focus area detected in a posting.

        A direct title match is sufficient. Description-only matches require
        multiple distinct indicators from the same category, reducing false
        positives from broad or interdisciplinary ECE postings.
        """

        title = str(job_data.get("title") or "").strip()
        raw_text = str(job_data.get("raw_text") or "").strip()

        selected_focus_areas = set(self.user_profile["exclude_focus_areas"])
        for focus_area, rule in EXCLUDED_FOCUS_AREA_RULES.items():
            if focus_area not in selected_focus_areas:
                continue
            if any(
                re.search(pattern, title, flags=re.IGNORECASE)
                for pattern in rule["title_patterns"]
            ):
                return focus_area

            content_matches = sum(
                1
                for pattern in rule["content_patterns"]
                if re.search(pattern, raw_text, flags=re.IGNORECASE)
            )

            if content_matches >= rule["minimum_content_matches"]:
                return focus_area

        return None
