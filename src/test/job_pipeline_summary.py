"""
Phases 3-6 - Job Pipeline Summary Test
Validates partitioned reports, reconciliation, and timing serialization.
"""

import json
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from src.job_pipeline import (
    JobPipeline,
    format_elapsed_time,
    parse_elapsed_time,
)
from src.job_agent_runner import JobAgentRunner
from src.test.data.user_profile import TEST_USER_PROFILE
from src.profile_loader import validate_user_profile
from src.main import (
    _done_job_files,
    _private_files,
    _redacted_command_arguments,
    _selected_report_paths,
    parse_arguments,
    print_final_summary,
)


class Stub:
    pass


def main() -> None:
    assert validate_user_profile(TEST_USER_PROFILE) is TEST_USER_PROFILE
    private_path_arguments = [
        "--private_data_path",
        "/tmp/job-agent-private/private_data",
    ]
    landing_url_arguments = [
        "--landing_url",
        "https://www.higheredjobs.com/myHigherEdJobs/Agent/"
        "viewagent.cfm?AgentID=123456",
    ]
    assert parse_arguments(
        ["--rpa", *private_path_arguments, *landing_url_arguments]
    ).rpa is True
    remote_arguments = parse_arguments(
        ["--remote", *private_path_arguments, *landing_url_arguments]
    )
    assert remote_arguments.remote is True
    assert str(_selected_report_paths(False)["report_dir"]).endswith(
        "live_runs/non_remote"
    )
    assert str(_selected_report_paths(True)["report_dir"]).endswith(
        "live_runs/remote"
    )
    windows_path = parse_arguments(
        [
            "--private_data_path",
            r"D:\Private\JobAgent\private_data",
            *landing_url_arguments,
        ]
    ).private_data_path
    assert str(windows_path) == (
        "/mnt/d/Private/JobAgent/private_data"
    )
    assert tuple(map(str, _private_files(windows_path))) == (
        "/mnt/d/Private/JobAgent/private_data/user_profile.toml",
        "/mnt/d/Private/JobAgent/private_data/applied_jobs.json",
        "/mnt/d/Private/JobAgent/private_data/closed_jobs.json",
    )
    assert tuple(map(str, _done_job_files(windows_path))) == (
        "/mnt/d/Private/JobAgent/private_data/applied_jobs.json",
        "/mnt/d/Private/JobAgent/private_data/closed_jobs.json",
    )
    assert _redacted_command_arguments(private_path_arguments) == [
        "--private_data_path",
        "<private-data-path>",
    ]
    assert parse_arguments(
        [
            "--done_jobs_path",
            "/tmp/job-agent-private/private_data",
            *landing_url_arguments,
        ]
    ).private_data_path == Path("/tmp/job-agent-private/private_data")
    for retired_argument in (
        "--application_document_agents",
        "--job_sequence_number",
    ):
        with redirect_stderr(StringIO()):
            try:
                parse_arguments(
                    [retired_argument, *private_path_arguments]
                )
            except SystemExit as error:
                assert error.code == 2
            else:
                raise AssertionError(
                    f"Retired argument remains accepted: {retired_argument}"
                )
    phase_6_remote = parse_arguments(
        ["--document_manager", "--remote", *private_path_arguments]
    )
    assert phase_6_remote.document_manager is True
    assert phase_6_remote.remote is True
    with redirect_stderr(StringIO()):
        try:
            parse_arguments(
                [
                    "--report_mode",
                    "append",
                    *private_path_arguments,
                    *landing_url_arguments,
                ]
            )
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError("Retired report mode remains accepted.")

    pipeline = JobPipeline(
        Stub(),
        Stub(),
        Stub(),
        TEST_USER_PROFILE,
    )
    jobs = [
        {"source_url": "a", "final_recommendation": "apply"},
        {"source_url": "b", "final_recommendation": "review"},
        {"source_url": "c", "final_recommendation": "skip"},
        {
            "source_url": "d",
            "final_recommendation": "skip",
            "skipped_before_llm": True,
        },
        {"source_url": "e", "final_recommendation": "manual_review"},
    ]
    result = {
        "jobs": jobs,
        "run_summary": {
            "jobs_discovered": 5,
            "jobs_sent_to_llm": 4,
            "jobs_skipped_before_llm": 1,
            "jobs_failed_llm": 1,
            "llm_utilization_percent": 80.0,
            "elapsed_time_sec": 10.0,
            "phase_4_elapsed_time_sec": 1.0,
            "phase_5_elapsed_time_sec": 8.0,
            "pipeline_overhead_time_sec": 1.0,
            "average_llm_time_sec": 2.0,
        },
    }

    # Preserve the recommendation-schema invariant that was formerly checked
    # by the removed live full-pipeline test. This synthetic set includes every
    # supported value, so the assertion cannot pass vacuously when all saved
    # HTML fixtures are filtered before analysis.
    allowed_recommendations = {
        "apply",
        "review",
        "skip",
        "manual_review",
    }
    assert all(
        job["final_recommendation"] in allowed_recommendations
        for job in jobs
    )

    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        analyzed = root / "analyzed"
        report_files = {
            "apply": analyzed / "apply_jobs.json",
            "review": analyzed / "review_jobs.json",
            "do_not_apply": analyzed / "do_not_apply_jobs.json",
            "skipped": root / "skipped_jobs.json",
            "unreachable": root / "unreachable_jobs.json",
        }
        category_reports = pipeline.save_partitioned_reports(
            result, report_files, "higheredjobs", datetime.now().astimezone()
        )
        stats_file = analyzed / "apply_jobs_stats.txt"
        pipeline.save_apply_jobs_stats(
            [
                {"job_sequence_number": 5, "state": "TX"},
                {"job_sequence_number": 2, "state": "NY"},
                {"job_sequence_number": 3, "state": "TX"},
            ],
            stats_file,
        )
        assert stats_file.read_text(encoding="utf-8") == (
            "State | Job sequence numbers\n"
            "------+---------------------\n"
            "NY    | 2\n"
            "TX    | 3, 5\n"
        )
        assert pipeline.create_apply_jobs_stats(
            [
                {"job_sequence_number": "r10", "state": "MI"},
                {"job_sequence_number": "r2", "state": "MI"},
            ]
        ).endswith("MI    | r2, r10\n")
        summary_file = root / "summary.json"
        summary = pipeline.save_summary_report(
            pipeline_result=result,
            category_reports=category_reports,
            output_file=summary_file,
            job_board="higheredjobs",
            report_files={**report_files, "summary": summary_file},
        )
        loaded = json.loads(summary_file.read_text(encoding="utf-8"))
        assert loaded == summary
        assert summary["job_counts"]["accounted_for"] == 5
        assert all(summary["validation"].values())
        assert summary["report_metadata"]["report_version"] == "1.2"
        assert summary["timing"]["phase_3_elapsed_time"] == "0 s"
        assert summary["timing"]["phase_4_elapsed_time"] == "1 s"
        assert summary["timing"]["phase_5_elapsed_time"] == "8 s"
        assert summary["timing"]["phase_6_elapsed_time"] == "0 s"
        assert summary["timing"]["total_elapsed_time"] == "10 s"
        assert not any(
            name.endswith("_sec") for name in summary["timing"]
        )
        assert summary["timing"]["llm_utilization_percent"] == 80.0

    assert format_elapsed_time(125.2) == "2 m 5.2 s"
    assert format_elapsed_time(5568.48) == "1 h 32 m 48.48 s"
    assert format_elapsed_time(3600) == "1 h 0 m 0 s"
    assert parse_elapsed_time("1 h 32 m 48.48 s") == 5568.48

    phase_output = StringIO()
    with redirect_stdout(phase_output):
        JobAgentRunner.print_completion(
            "PHASE 5 — Job Analysis Agent",
            "Test completion.",
            5047.6,
        )
    assert "Elapsed time: 1 h 24 m 7.6 s." in phase_output.getvalue()

    final_output = StringIO()
    with redirect_stdout(final_output):
        print_final_summary(
            {
                "pipeline_result": {
                    "run_summary": {"average_llm_time_sec": 73.15}
                },
                "summary_report": {
                    "job_counts": {
                        "discovered": 281,
                        "apply": 15,
                        "review": 26,
                        "do_not_apply": 27,
                        "skipped": 212,
                        "unreachable": 1,
                    }
                },
                "total_elapsed_time_sec": 6088.31,
                "report_paths": _selected_report_paths(False),
            }
        )
    console_text = final_output.getvalue()
    assert "Average LLM time: 1 m 13.15 s" in console_text
    assert "Total run time  : 1 h 41 m 28.31 s" in console_text

    print("Job-pipeline summary test passed.")


if __name__ == "__main__":
    main()
