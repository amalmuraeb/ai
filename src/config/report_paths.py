"""
Job-Agent Report Paths
Defines staging and published report destinations across phases.
"""

from pathlib import Path


DEBUG_SEPARATOR_WIDTH = 72

HIGHEREDJOBS_REPORTS_DIR = Path(
    "output/job_boards/higheredjobs/reports"
)

def build_report_paths(report_dir: Path) -> dict[str, Path]:
    """Return the complete report-file layout for one pipeline run."""

    analyzed_dir = report_dir / "analyzed"

    return {
        "report_dir": report_dir,
        "analyzed_dir": analyzed_dir,
        "apply": analyzed_dir / "apply_jobs.json",
        "apply_stats": analyzed_dir / "apply_jobs_stats.txt",
        "review": analyzed_dir / "review_jobs.json",
        "do_not_apply": analyzed_dir / "do_not_apply_jobs.json",
        "skipped": report_dir / "skipped_jobs.json",
        "unreachable": report_dir / "unreachable_jobs.json",
        "document_manager": report_dir / "document_manager.json",
        "applied": report_dir / "applied_jobs.json",
        "summary": report_dir / "summary.json",
        "log": report_dir / "log.txt",
    }


# Output used for normal Job-Agent execution through src.main.
# Each live execution overwrites the previous live-run reports.
HIGHEREDJOBS_LIVE_RUN_REPORT_DIR = (
    HIGHEREDJOBS_REPORTS_DIR / "live_runs"
)
HIGHEREDJOBS_LIVE_RUN_REPORT_PATHS = build_report_paths(
    HIGHEREDJOBS_LIVE_RUN_REPORT_DIR
)

# Temporary output used to build and validate a normal Job-Agent run
# before replacing the last successful live-run reports.
HIGHEREDJOBS_LIVE_RUN_STAGING_DIR = (
    HIGHEREDJOBS_REPORTS_DIR / ".live_runs_staging"
)
HIGHEREDJOBS_LIVE_RUN_STAGING_PATHS = build_report_paths(
    HIGHEREDJOBS_LIVE_RUN_STAGING_DIR
)

# Phase 6 isolation stages its report plus the narrowly updated full-run
# summary. It must not replace upstream category reports or the run log.
HIGHEREDJOBS_DOCUMENT_MANAGER_STAGING_FILE = (
    HIGHEREDJOBS_REPORTS_DIR / ".document_manager_staging.json"
)
HIGHEREDJOBS_DOCUMENT_MANAGER_SUMMARY_STAGING_FILE = (
    HIGHEREDJOBS_REPORTS_DIR / ".document_manager_summary_staging.json"
)
HIGHEREDJOBS_DOCUMENT_MANAGER_APPLY_STAGING_FILE = (
    HIGHEREDJOBS_REPORTS_DIR / ".document_manager_apply_staging.json"
)
HIGHEREDJOBS_DOCUMENT_MANAGER_APPLY_STATS_STAGING_FILE = (
    HIGHEREDJOBS_REPORTS_DIR / ".document_manager_apply_stats_staging.txt"
)
# Temporary output for the combined isolated Reader, Provisioner, and
# Analysis run. Downstream artifacts are preserved during publication.
HIGHEREDJOBS_RPA_STAGING_DIR = HIGHEREDJOBS_REPORTS_DIR / ".rpa_staging"
HIGHEREDJOBS_RPA_STAGING_PATHS = build_report_paths(
    HIGHEREDJOBS_RPA_STAGING_DIR
)
