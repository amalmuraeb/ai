"""
Job-Agent Report Paths
Defines staging and published report destinations across phases.
"""

import json
import shutil
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


HIGHEREDJOBS_LIVE_RUNS_DIR = HIGHEREDJOBS_REPORTS_DIR / "live_runs"


def _normalize_migrated_non_remote_reports(target: Path) -> None:
    """Stamp migrated reports and correct their former flat output paths."""

    for report_file in target.rglob("*.json"):
        report = json.loads(report_file.read_text(encoding="utf-8"))
        changed = False
        metadata = report.get("report_metadata")
        if (
            isinstance(metadata, dict)
            and metadata.get("job_scope") != "non_remote"
        ):
            metadata["job_scope"] = "non_remote"
            changed = True
        if report_file.name == "summary.json":
            report_files = report.get("report_files", {})
            for name, path in report_files.items():
                if isinstance(path, str):
                    migrated_path = path.replace(
                        "reports/live_runs/",
                        "reports/live_runs/non_remote/",
                    )
                    if migrated_path != path:
                        report_files[name] = migrated_path
                        changed = True
        if changed:
            report_file.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


def build_live_scope_paths(remote: bool = False) -> dict[str, object]:
    """Return published and staging paths for one independent job scope."""

    scope = "remote" if remote else "non_remote"
    scope_stem = scope.replace("_", "-")
    live_dir = HIGHEREDJOBS_LIVE_RUNS_DIR / scope
    staging_dir = HIGHEREDJOBS_REPORTS_DIR / f".{scope_stem}_live_staging"
    rpa_staging_dir = HIGHEREDJOBS_REPORTS_DIR / f".{scope_stem}_rpa_staging"
    phase_6_prefix = HIGHEREDJOBS_REPORTS_DIR / f".{scope_stem}_phase_6"

    return {
        "scope": scope,
        "live": build_report_paths(live_dir),
        "staging": build_report_paths(staging_dir),
        "rpa_staging": build_report_paths(rpa_staging_dir),
        "document_manager_staging": phase_6_prefix.with_suffix(".json"),
        "document_manager_summary_staging": phase_6_prefix.with_name(
            f"{phase_6_prefix.name}_summary.json"
        ),
        "document_manager_apply_staging": phase_6_prefix.with_name(
            f"{phase_6_prefix.name}_apply.json"
        ),
        "document_manager_apply_stats_staging": phase_6_prefix.with_name(
            f"{phase_6_prefix.name}_apply_stats.txt"
        ),
    }


def migrate_legacy_non_remote_reports() -> None:
    """Move the former flat live-run layout into the non-remote channel."""

    target = HIGHEREDJOBS_LIVE_RUNS_DIR / "non_remote"
    legacy_names = (
        "analyzed",
        "document_manager.json",
        "skipped_jobs.json",
        "unreachable_jobs.json",
        "summary.json",
        "log.txt",
    )
    legacy_items = [
        HIGHEREDJOBS_LIVE_RUNS_DIR / name
        for name in legacy_names
        if (HIGHEREDJOBS_LIVE_RUNS_DIR / name).exists()
    ]
    if target.exists():
        _normalize_migrated_non_remote_reports(target)
        return
    if not legacy_items:
        return

    migration = HIGHEREDJOBS_REPORTS_DIR / ".non-remote_migration"
    if migration.exists():
        shutil.rmtree(migration)
    migration.mkdir(parents=True)
    try:
        for item in legacy_items:
            item.replace(migration / item.name)
        migration.replace(target)
        _normalize_migrated_non_remote_reports(target)
    except BaseException:
        for item in migration.iterdir() if migration.exists() else ():
            item.replace(HIGHEREDJOBS_LIVE_RUNS_DIR / item.name)
        raise
    finally:
        if migration.exists():
            shutil.rmtree(migration)
