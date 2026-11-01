"""
Job-Agent Regression Suite
Runs isolated deterministic tests while excluding live dependencies.
"""

import subprocess
import sys
from pathlib import Path


REGRESSION_MODULES = (
    "src.test.application_history",
    "src.test.job_provisioner",
    "src.test.job_pipeline_summary",
    "src.test.document_manager",
    "src.test.document_manager_isolation",
    "src.test.document_requirement_agent",
    "src.test.job_boards.higheredjobs.document_source",
    "src.test.job_boards.higheredjobs.pagination",
    "src.test.job_boards.higheredjobs.sample_html_full_pipeline",
)


def main() -> int:
    project_root = Path(__file__).resolve().parents[2]
    failures = []

    print("=" * 60)
    print("Job-Agent deterministic regression suite")
    print("=" * 60)

    for module in REGRESSION_MODULES:
        print(f"\nRunning: python -m {module}", flush=True)
        completed = subprocess.run(
            [sys.executable, "-m", module],
            cwd=project_root,
            check=False,
        )

        if completed.returncode != 0:
            failures.append((module, completed.returncode))

    print("\n" + "=" * 60)

    if failures:
        print("Job-Agent regression suite FAILED")
        for module, returncode in failures:
            print(f"- {module}: exit code {returncode}")
        return 1

    print(
        "Job-Agent regression suite passed: "
        f"{len(REGRESSION_MODULES)} test modules."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
