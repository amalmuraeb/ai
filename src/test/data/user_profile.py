"""Synthetic user profile shared by deterministic public tests."""

from src.config.job_provisioner import (
    EXCLUDED_FOCUS_AREA_RULES,
    EXCLUDED_ROLES_PATTERNS,
)

TEST_USER_PROFILE = {
    "target_roles": ["Example engineering role"],
    "role_scope": {"academic_faculty_allowed": True},
    "employment_type": {
        "allowed_types": ["full-time"],
        "exclude_adjunct": True,
        "exclude_postdoc": True,
        "exclude_visiting": True,
    },
    "discipline_focus": ["Example engineering discipline"],
    "work_constraints": {
        "remote_preferred": False,
        "location_flexibility": "Example region",
    },
    "salary_constraint": {
        "minimum_salary_usd": 105000,
        "hard_requirement": True,
    },
    "application_constraints": {
        "closing_date_soon_threshold_months": 4,
        "skip_if_closing_date_soon": True,
    },
    "ranking_constraints": {
        "apply_min_fit_score": 92,
        "review_min_fit_score": 75,
    },
    # Selecting every catalog entry verifies the public matching engine. This
    # fixture is intentionally synthetic and is not a real user's profile.
    "exclude_industries": ["Military and defense"],
    "exclude_institution_orientations": [
        "Religious mission or affiliation"
    ],
    "exclude_focus_areas": list(EXCLUDED_FOCUS_AREA_RULES),
    "exclude_roles": list(EXCLUDED_ROLES_PATTERNS),
}
