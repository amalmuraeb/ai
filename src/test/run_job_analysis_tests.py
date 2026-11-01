"""
Phase 5 - Job Analysis Agent Test
Exercises structured Ollama analysis across representative sample jobs.
"""

from src.job_analysis_agent import JobAnalysisAgent
from src.json_utils import parse_json_response
from src.test.sample_jobs import (
    GENERAL_ENGINEERING_JOB,
    SOFTWARE_PLATFORM_JOB,
    RESEARCH_ENGINEERING_JOB,
)
from src.test.data.user_profile import TEST_USER_PROFILE


job_agent = JobAnalysisAgent(TEST_USER_PROFILE)

test_cases = [
    ("General engineering job", GENERAL_ENGINEERING_JOB),
    ("Software platform job", SOFTWARE_PLATFORM_JOB),
    ("Research engineering job", RESEARCH_ENGINEERING_JOB),
]

for name, job in test_cases:
    result = job_agent.run(job)
    data = parse_json_response(result)

    print("\n==============================")
    print(name)
    print("Recommendation:", data["final_recommendation"])
    print("Fit score:", data["fit_score"])
    print("Risk flags:", data["risk_flags"])
