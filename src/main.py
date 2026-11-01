"""
Job-Agent Production Entry Point
Runs the configured workflow and presents its final status.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.config.report_paths import (
    build_live_scope_paths,
    migrate_legacy_non_remote_reports,
)
from src.job_boards.higheredjobs.runner import (
    run_live_document_manager,
    run_live_job_agent,
    run_live_rpa,
)
from src.job_pipeline import format_elapsed_time
from src.profile_loader import load_user_profile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _selected_report_paths(remote=False):
    """Return the published paths for the selected job scope."""
    return build_live_scope_paths(remote)["live"]


def _private_data_path(value):
    """Normalize and validate the external private-data directory."""
    raw_path = str(value).strip()
    windows_match = re.fullmatch(
        r"([A-Za-z]):[\\/](.+)",
        raw_path,
    )
    if windows_match:
        drive, remainder = windows_match.groups()
        path = Path("/mnt") / drive.lower() / Path(
            remainder.replace("\\", "/")
        )
    else:
        path = Path(raw_path).expanduser()

    if not path.is_absolute():
        raise argparse.ArgumentTypeError(
            "--private_data_path must be an absolute Windows or WSL path."
        )
    if path.resolve(strict=False).is_relative_to(PROJECT_ROOT):
        raise argparse.ArgumentTypeError(
            "--private_data_path must be outside the Job-Agent repository."
        )
    return path


def _private_files(private_data_path):
    """Return private profile and history paths selected by the user."""
    return (
        private_data_path / "user_profile.toml",
        private_data_path / "applied_jobs.json",
        private_data_path / "closed_jobs.json",
    )


def _done_job_files(private_data_path):
    """Return the two private history files in the user-selected directory."""
    _, applied, closed = _private_files(private_data_path)
    return applied, closed


def _higheredjobs_landing_url(value):
    """Validate a user-supplied HigherEdJobs saved-alert results URL."""
    url = str(value).strip()
    parsed = urlparse(url)
    query = {
        name.casefold(): values
        for name, values in parse_qs(parsed.query).items()
    }
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"higheredjobs.com", "www.higheredjobs.com"}
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.casefold().endswith(
            "/myhigheredjobs/agent/viewagent.cfm"
        )
        or not query.get("agentid")
    ):
        raise argparse.ArgumentTypeError(
            "--landing_url must be an HTTPS HigherEdJobs saved-alert URL "
            "containing AgentID."
        )
    return url


def _redacted_command_arguments(command_arguments):
    """Hide the private archive location from the repository run log."""
    redacted = []
    option_labels = {
        "--private_data_path": "<private-data-path>",
        "--private-data-path": "<private-data-path>",
        "--done_jobs_path": "<private-done-jobs-path>",
        "--done-jobs-path": "<private-done-jobs-path>",
    }
    redacted_value = None
    for argument in command_arguments:
        if redacted_value is not None:
            redacted.append(redacted_value)
            redacted_value = None
        elif argument in option_labels:
            redacted.append(argument)
            redacted_value = option_labels[argument]
        elif any(
            argument.startswith(f"{option}=")
            for option in option_labels
        ):
            option = argument.split("=", 1)[0]
            redacted.append(
                option + "=" + option_labels[option]
            )
        else:
            redacted.append(argument)
    return redacted


def _reset_run_log(arguments, command_arguments, report_paths) -> None:
    """Start a fresh log for every public Job-Agent invocation."""
    mode_details = []
    if arguments.remote:
        mode_details.append("remote alert")
    detail_suffix = (
        f" ({', '.join(mode_details)})" if mode_details else ""
    )
    if arguments.document_manager:
        mode = "Phase 6 only"
    elif arguments.rpa:
        mode = "Phases 3-5 RPA" + detail_suffix
    else:
        mode = "Complete Job-Agent" + detail_suffix
    log_file = report_paths["log"]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        "Job-Agent run log\n"
        f"Started: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
        f"Mode: {mode}\n"
        "Command: python -m src.main "
        f"{' '.join(_redacted_command_arguments(command_arguments))}\n\n",
        encoding="utf-8",
    )


def _append_run_log(message, report_paths) -> None:
    """Append one current-run event without retaining historical runs."""
    with report_paths["log"].open("a", encoding="utf-8") as log_file:
        log_file.write(message.rstrip() + "\n")


def print_final_summary(run_result: dict) -> None:
    """Print the concise normal-run completion summary."""

    run_summary = run_result["pipeline_result"]["run_summary"]
    job_counts = run_result["summary_report"]["job_counts"]

    print("\n" + "=" * 60)
    print("Job-Agent run complete")
    print("=" * 60)
    print(f"Jobs discovered : {job_counts['discovered']}")
    print(f"Apply           : {job_counts['apply']}")
    print(f"Review          : {job_counts['review']}")
    print(f"Do Not Apply    : {job_counts['do_not_apply']}")
    print(f"Skipped         : {job_counts['skipped']}")
    print(f"Unreachable     : {job_counts['unreachable']}")
    print(
        f"Average LLM time: "
        f"{format_elapsed_time(run_summary['average_llm_time_sec'])}"
    )
    print(
        f"Total run time  : "
        f"{format_elapsed_time(run_result['total_elapsed_time_sec'])}"
    )
    report_paths = run_result["report_paths"]
    print(f"Reports         : {report_paths['report_dir']}")
    print(f"Summary         : {report_paths['summary']}")
    print(f"Run log         : {report_paths['log']}")
    print(f"Phase 6 report  : {report_paths['document_manager']}")


def parse_arguments(argv=None):
    """Parse normal-run and isolated-phase command options."""
    parser = argparse.ArgumentParser(description="Run the Job-Agent.")
    run_mode = parser.add_mutually_exclusive_group()
    run_mode.add_argument(
        "--document_manager",
        action="store_true",
        help=(
            "Run only Phase 6 using the existing Phase 5 apply report."
        ),
    )
    parser.add_argument(
        "--private_data_path",
        "--private-data-path",
        "--done_jobs_path",
        "--done-jobs-path",
        dest="private_data_path",
        required=True,
        type=_private_data_path,
        help=(
            "Absolute Windows or WSL path to the private directory that "
            "contains user_profile.toml, applied_jobs.json, and "
            "closed_jobs.json; the directory must be outside this "
            "repository. The --done_jobs_path spelling is retained as a "
            "compatibility alias."
        ),
    )
    parser.add_argument(
        "--landing_url",
        "--landing-url",
        type=_higheredjobs_landing_url,
        help=(
            "HigherEdJobs saved-alert results URL. Required for complete "
            "and --rpa runs; Phase 6 uses saved job URLs directly."
        ),
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help=(
            "Run the remote-job channel and use live_runs/remote reports. "
            "Without this option, live_runs/non_remote is used."
        ),
    )
    run_mode.add_argument(
        "--rpa",
        action="store_true",
        help=(
            "Run only Phases 3-5: Reader, Provisioner, and Analysis."
        ),
    )
    arguments = parser.parse_args(argv)
    if not arguments.document_manager and not arguments.landing_url:
        parser.error(
            "--landing_url is required for complete and --rpa runs."
        )
    return arguments


def main(argv=None) -> int:
    """Execute the Job Agent and return a process exit status."""

    command_arguments = list(argv) if argv is not None else sys.argv[1:]
    arguments = parse_arguments(command_arguments)
    migrate_legacy_non_remote_reports()
    report_paths = _selected_report_paths(arguments.remote)
    _, applied_jobs_path, closed_jobs_path = _private_files(
        arguments.private_data_path
    )
    _reset_run_log(arguments, command_arguments, report_paths)
    try:
        user_profile = load_user_profile(arguments.private_data_path)
    except Exception as error:
        print(
            "\nJob-Agent private profile load failed: "
            f"{type(error).__name__}: {error}"
        )
        _append_run_log(
            "FAILED: Private profile load failed: "
            f"{type(error).__name__}: {error}",
            report_paths,
        )
        return 1

    if arguments.document_manager:
        print("=" * 60)
        print("Starting Job-Agent Phase 6 only")
        print("Input: existing HigherEdJobs apply_jobs.json")
        print(f"Scope: {'remote' if arguments.remote else 'non-remote'}")
        print(f"Output: {report_paths['document_manager']}")
        print("=" * 60)

        try:
            run_live_document_manager(
                applied_jobs_path,
                closed_jobs_path,
                user_profile,
                arguments.remote,
            )
        except KeyboardInterrupt:
            print("\nJob-Agent Phase 6 run interrupted by user.")
            _append_run_log(
                "INTERRUPTED: Phase 6 run interrupted by user.",
                report_paths,
            )
            return 130
        except Exception as error:
            print(
                "\nJob-Agent Phase 6 run failed: "
                f"{type(error).__name__}: {error}"
            )
            _append_run_log(
                "FAILED: Job-Agent Phase 6 run failed: "
                f"{type(error).__name__}: {error}",
                report_paths,
            )
            return 1

        _append_run_log("SUCCESS: Phase 6 completed.", report_paths)
        print(f"Phase 6 report  : {report_paths['document_manager']}")
        return 0

    if arguments.rpa:
        print("=" * 60)
        print("Starting Job-Agent RPA run")
        print("Phases: 3 — Reader, 4 — Provisioner, 5 — Analysis")
        print(f"Scope: {'remote' if arguments.remote else 'non-remote'}")
        print(f"Reports: {report_paths['report_dir']}")
        print("=" * 60)

        try:
            run_result = run_live_rpa(
                applied_jobs_path,
                closed_jobs_path,
                user_profile,
                arguments.landing_url,
                arguments.remote,
            )
        except KeyboardInterrupt:
            print("\nJob-Agent RPA run interrupted by user.")
            _append_run_log(
                "INTERRUPTED: RPA run interrupted by user.",
                report_paths,
            )
            return 130
        except Exception as error:
            print(
                "\nJob-Agent RPA run failed: "
                f"{type(error).__name__}: {error}"
            )
            _append_run_log(
                "FAILED: Job-Agent RPA run failed: "
                f"{type(error).__name__}: {error}",
                report_paths,
            )
            return 1

        _append_run_log(
            "SUCCESS: Phases 3-5 RPA completed.",
            report_paths,
        )
        print_final_summary(run_result)
        return 0

    print("=" * 60)
    print("Starting Job-Agent")
    print("Source: HigherEdJobs")
    print(f"Scope: {'remote' if arguments.remote else 'non-remote'}")
    print(f"Reports: {report_paths['report_dir']}")
    print("=" * 60)

    try:
        run_result = run_live_job_agent(
            applied_jobs_path,
            closed_jobs_path,
            user_profile,
            arguments.landing_url,
            arguments.remote,
        )
    except KeyboardInterrupt:
        print("\nJob-Agent run interrupted by user.")
        _append_run_log(
            "INTERRUPTED: Complete Job-Agent run interrupted.",
            report_paths,
        )
        return 130
    except Exception as error:
        print(
            "\nJob-Agent run failed: "
            f"{type(error).__name__}: {error}"
        )
        _append_run_log(
            "FAILED: Job-Agent run failed: "
            f"{type(error).__name__}: {error}",
            report_paths,
        )
        return 1

    _append_run_log(
        "SUCCESS: Complete Job-Agent run completed.",
        report_paths,
    )
    print_final_summary(run_result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
