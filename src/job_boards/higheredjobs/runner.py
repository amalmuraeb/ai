"""
Phases 3-6 - HigherEdJobs Runner
Specializes the shared runner for HigherEdJobs production execution.
"""

from src.config.report_paths import build_live_scope_paths
from src.document_manager import DocumentManager
from src.document_requirement_agent import DocumentRequirementAgent
from src.job_agent_runner import JobAgentRunner
from src.job_boards.higheredjobs.document_source import (
    HigherEdJobsDocumentSource,
)
from src.job_boards.higheredjobs.source import HigherEdJobsSource


class HigherEdJobsRunner(JobAgentRunner):
    """Configure the shared runner for the HigherEdJobs source."""

    def __init__(
        self,
        applied_jobs_path,
        closed_jobs_path,
        user_profile,
        landing_url=None,
        remote_alert=False,
    ):
        super().__init__(user_profile, remote=remote_alert)
        self.applied_jobs_path = applied_jobs_path
        self.closed_jobs_path = closed_jobs_path
        self.landing_url = landing_url
        self.remote_alert = remote_alert
        self.scope_paths = build_live_scope_paths(remote_alert)
        self.applied_jobs_staging_path = applied_jobs_path.with_name(
            ".applied_jobs_staging.json"
        )

    def _live_paths(self):
        paths = dict(self.scope_paths["live"])
        paths["other_document_manager"] = build_live_scope_paths(
            not self.remote_alert
        )["live"]["document_manager"]
        paths["applied"] = self.applied_jobs_path
        paths["closed"] = self.closed_jobs_path
        return paths

    def _staging_paths(self, configured_paths):
        paths = dict(configured_paths)
        paths["applied"] = self.applied_jobs_staging_path
        paths["closed"] = self.closed_jobs_path
        return paths

    def create_source(self) -> HigherEdJobsSource:
        return HigherEdJobsSource(
            landing_url=self.landing_url,
            remote_alert=self.remote_alert,
        )

    def load_document_postings(self, apply_jobs):
        """Retrieve current HigherEdJobs posting bodies for Phase 6."""
        return HigherEdJobsDocumentSource().load_postings(apply_jobs)

    def create_document_manager(self) -> DocumentManager:
        """Enable controlled Ollama fallback for live Phase 6 runs."""
        return DocumentManager(
            requirement_agent=DocumentRequirementAgent()
        )

    def run_live(self) -> dict:
        """Build, validate, and publish a normal Job-Agent live run."""

        return self.run_transactional(
            staging_paths=self._staging_paths(
                self.scope_paths["staging"]
            ),
            live_paths=self._live_paths(),
            pipeline_name="Job-Agent Live Run",
            report_title="JOB-AGENT LIVE RUN LOG",
        )

    def run_live_document_manager(self) -> dict:
        """Run Phase 6 from published Phase 5 reports only."""
        return self.run_document_manager(
            apply_report_path=self._live_paths()["apply"],
            staging_output=self.scope_paths["document_manager_staging"],
            staging_summary=(
                self.scope_paths["document_manager_summary_staging"]
            ),
            staging_apply=self.scope_paths["document_manager_apply_staging"],
            staging_applied=self.applied_jobs_staging_path,
            staging_apply_stats=(
                self.scope_paths[
                    "document_manager_apply_stats_staging"
                ]
            ),
            published_output=self._live_paths()[
                "document_manager"
            ],
            published_summary=self._live_paths()["summary"],
            published_applied=self.applied_jobs_path,
            published_closed=self.closed_jobs_path,
            published_apply_stats=self._live_paths()["apply_stats"],
            job_board="higheredjobs",
            pipeline_name="Job-Agent Isolated Phase 6 Run",
        )

    def run_live_rpa(self) -> dict:
        """Run only the Reader, Provisioner, and Analysis phases."""
        return self.run_rpa_transactional(
            staging_paths=self._staging_paths(
                self.scope_paths["rpa_staging"]
            ),
            live_paths=self._live_paths(),
            pipeline_name="Job-Agent RPA Run",
            report_title="JOB-AGENT RPA RUN LOG",
        )


def run_live_job_agent(
    applied_jobs_path,
    closed_jobs_path,
    user_profile,
    landing_url,
    remote_alert=False,
) -> dict:
    """Compatibility function for the normal Job-Agent entry point."""

    return HigherEdJobsRunner(
        applied_jobs_path,
        closed_jobs_path,
        user_profile,
        landing_url,
        remote_alert,
    ).run_live()


def run_live_document_manager(
    applied_jobs_path,
    closed_jobs_path,
    user_profile,
    remote_alert=False,
) -> dict:
    """Compatibility function for isolated Phase 6 execution."""
    return HigherEdJobsRunner(
        applied_jobs_path,
        closed_jobs_path,
        user_profile,
        remote_alert=remote_alert,
    ).run_live_document_manager()


def run_live_rpa(
    applied_jobs_path,
    closed_jobs_path,
    user_profile,
    landing_url,
    remote_alert=False,
) -> dict:
    """Compatibility function for combined Phase 3–5 execution."""
    return HigherEdJobsRunner(
        applied_jobs_path,
        closed_jobs_path,
        user_profile,
        landing_url,
        remote_alert,
    ).run_live_rpa()
