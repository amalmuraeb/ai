"""
Phases 5-6 - Application History
Maintains durable job identities and manual application state across runs.
"""

from copy import deepcopy
from datetime import date, datetime

from src.version import __version__


class ApplicationHistory:
    """Reconcile fresh recommendations with persistent application reports."""

    @staticmethod
    def _url(item):
        job = item.get("job") if isinstance(item, dict) else None
        if isinstance(job, dict):
            return job.get("source_url")
        return item.get("source_url") if isinstance(item, dict) else None

    @staticmethod
    def _closing_date(job):
        value = job.get("closing_date")
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except ValueError:
            return None

    @classmethod
    def _expired(cls, job, today):
        closing_date = cls._closing_date(job)
        return closing_date is not None and closing_date < today

    @staticmethod
    def _sequenced_job(job, sequence_number):
        job = deepcopy(job)
        job.pop("job_sequence_number", None)
        return {"job_sequence_number": sequence_number, **job}

    @staticmethod
    def _with_remote(job):
        """Normalize legacy history records to the current report schema."""
        job = deepcopy(job)
        job["remote?"] = "Yes" if job.get("remote?") == "Yes" else "No"
        return job

    @staticmethod
    def _sequence_counter(value, remote):
        """Return the numeric counter when a sequence belongs to the scope."""
        if remote:
            if isinstance(value, str) and value.startswith("r"):
                suffix = value[1:]
                return int(suffix) if suffix.isdigit() else None
            return None
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _sequence_value(counter, remote):
        return f"r{counter}" if remote else counter

    @staticmethod
    def _applied_entry(plan, apply_job):
        """Return the compact permanent record needed after application."""
        tracked = plan["job"]
        return {
            "job": {
                "job_sequence_number": tracked["job_sequence_number"],
                "title": tracked["title"],
                "applied?": "Yes",
                "application_date": tracked.get("application_date"),
                "company": tracked.get("company"),
                "city": tracked.get("city"),
                "state": tracked.get("state"),
                "remote?": tracked.get("remote?", "No"),
                "source_url": tracked.get("source_url"),
                "focus_areas": deepcopy(
                    apply_job.get("focus_areas", [])
                ),
                "must_have_skills": deepcopy(
                    apply_job.get("must_have_skills", [])
                ),
            }
        }

    @staticmethod
    def empty_applied_report(job_board="unknown", pipeline_name="Job-Agent"):
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        return {
            "report_metadata": {
                "report_name": "applied_jobs.json",
                "report_version": "1.0",
                "software_version": __version__,
                "pipeline": pipeline_name,
                "job_board": job_board,
                "report_created_at": now,
            },
            "job_count": 0,
            "jobs": [],
        }

    def reconcile(
        self,
        fresh_apply_jobs,
        *,
        previous_apply_report=None,
        previous_document_report=None,
        previous_applied_report=None,
        deterministically_excluded_urls=None,
        privately_suppressed_urls=None,
        job_board="unknown",
        pipeline_name="Job-Agent",
        today=None,
        remote=False,
    ):
        """Return persistent apply/document state and newly discovered jobs."""
        today = today or date.today()
        deterministically_excluded_urls = set(
            deterministically_excluded_urls or ()
        )
        privately_suppressed_urls = set(privately_suppressed_urls or ())
        excluded_urls = (
            deterministically_excluded_urls | privately_suppressed_urls
        )
        previous_apply_report = previous_apply_report or {"jobs": []}
        previous_document_report = previous_document_report or {"jobs": []}
        applied_report = deepcopy(
            previous_applied_report
            or self.empty_applied_report(job_board, pipeline_name)
        )
        empty_applied = self.empty_applied_report(job_board, pipeline_name)
        applied_report.setdefault(
            "report_metadata",
            empty_applied["report_metadata"],
        )
        applied_report.setdefault("jobs", [])

        previous_apply = {
            self._url(job): self._with_remote(job)
            for job in previous_apply_report.get("jobs", [])
            if self._url(job)
        }
        applied_entries = {
            self._url(entry): {
                **deepcopy(entry),
                "job": self._with_remote(entry.get("job", {})),
            }
            for entry in applied_report.get("jobs", [])
            if self._url(entry)
        }
        retained_plans = {}

        sequence_numbers = [
            counter
            for value in (
                (
                    entry.get("job", {}).get("job_sequence_number")
                    if "job" in entry
                    else entry.get("job_sequence_number")
                )
                for entry in (
                    list(previous_document_report.get("jobs", []))
                    + list(applied_entries.values())
                    + list(previous_apply.values())
                )
            )
            if (counter := self._sequence_counter(value, remote)) is not None
        ]
        scoped_counters = applied_report.get("report_metadata", {}).get(
            "last_job_sequence_numbers",
            {},
        )
        scoped_counter = scoped_counters.get(
            "remote" if remote else "non_remote",
            0,
        )
        counter_values = [
            self._sequence_counter(
                previous_document_report.get("report_metadata", {}).get(
                    "last_job_sequence_number",
                    0,
                ),
                remote,
            ),
            scoped_counter if isinstance(scoped_counter, int) else 0,
            *sequence_numbers,
        ]
        if not remote:
            legacy_counter = applied_report.get("report_metadata", {}).get(
                "last_job_sequence_number",
                0,
            )
            if isinstance(legacy_counter, int):
                counter_values.append(legacy_counter)
        last_counter = max(
            value for value in counter_values if isinstance(value, int)
        )

        for plan in previous_document_report.get("jobs", []):
            url = self._url(plan)
            if not url:
                continue
            if url in excluded_urls:
                continue
            plan = deepcopy(plan)
            tracking = plan.get("job", {})
            tracking["remote?"] = (
                "Yes" if tracking.get("remote?") == "Yes" else "No"
            )
            if tracking.get("applied?") == "Yes":
                applied_entries[url] = self._applied_entry(
                    plan,
                    previous_apply.get(url, {}),
                )
                continue
            prior_apply = previous_apply.get(url, {})
            if self._expired(prior_apply, today):
                continue
            retained_plans[url] = plan

        applied_urls = set(applied_entries)
        persistent_apply = []
        for url, plan in retained_plans.items():
            prior = previous_apply.get(url)
            if prior is not None:
                persistent_apply.append(prior)

        new_jobs = []
        seen_fresh = set()
        for fresh_job in fresh_apply_jobs:
            fresh_job = self._with_remote(fresh_job)
            url = self._url(fresh_job)
            if (
                not url
                or url in seen_fresh
                or url in applied_urls
                or url in privately_suppressed_urls
            ):
                continue
            seen_fresh.add(url)
            if self._expired(fresh_job, today):
                continue
            if url in retained_plans:
                continue
            last_counter += 1
            sequenced = self._sequenced_job(
                fresh_job,
                self._sequence_value(last_counter, remote),
            )
            persistent_apply.append(sequenced)
            new_jobs.append(sequenced)

        applied_report["report_metadata"].update(
            {
                "report_name": "applied_jobs.json",
                "report_version": "1.0",
                "software_version": __version__,
                "pipeline": pipeline_name,
                "job_board": job_board,
                "report_created_at": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
            }
        )
        counters = applied_report["report_metadata"].setdefault(
            "last_job_sequence_numbers",
            {},
        )
        counters["remote" if remote else "non_remote"] = last_counter
        if not remote:
            # Retain the legacy field for readers of older private archives.
            applied_report["report_metadata"][
                "last_job_sequence_number"
            ] = last_counter
        applied_report["jobs"] = list(applied_entries.values())
        applied_report["job_count"] = len(applied_report["jobs"])

        return {
            "apply_jobs": persistent_apply,
            "retained_document_plans": list(retained_plans.values()),
            "new_apply_jobs": new_jobs,
            "applied_report": applied_report,
            "applied_urls": applied_urls,
            "retained_urls": set(retained_plans),
            "last_job_sequence_number": self._sequence_value(
                last_counter,
                remote,
            ),
        }
