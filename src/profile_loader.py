"""
Core Infrastructure - Private Profile Loader
Loads and validates user-specific job-search preferences outside the repo.
"""

import tomllib
from pathlib import Path


PROFILE_FILENAME = "user_profile.toml"

REQUIRED_LIST_FIELDS = (
    "target_roles",
    "discipline_focus",
    "exclude_industries",
    "exclude_institution_orientations",
    "exclude_focus_areas",
    "exclude_roles",
)

REQUIRED_SECTIONS = {
    "role_scope": ("academic_faculty_allowed",),
    "employment_type": (
        "allowed_types",
        "exclude_adjunct",
        "exclude_postdoc",
        "exclude_visiting",
    ),
    "work_constraints": ("remote_preferred", "location_flexibility"),
    "salary_constraint": ("minimum_salary_usd", "hard_requirement"),
    "application_constraints": (
        "closing_date_soon_threshold_months",
        "skip_if_closing_date_soon",
    ),
    "ranking_constraints": ("apply_min_fit_score", "review_min_fit_score"),
}


def validate_user_profile(profile: dict) -> dict:
    """Validate the private profile contract and return the profile."""
    if not isinstance(profile, dict):
        raise ValueError("User profile must be a TOML table.")

    missing = [field for field in REQUIRED_LIST_FIELDS if field not in profile]
    for section, fields in REQUIRED_SECTIONS.items():
        value = profile.get(section)
        if not isinstance(value, dict):
            missing.append(section)
            continue
        missing.extend(
            f"{section}.{field}" for field in fields if field not in value
        )
    if missing:
        raise ValueError(
            "User profile is missing required field(s): "
            + ", ".join(missing)
        )

    for field in REQUIRED_LIST_FIELDS:
        if not isinstance(profile[field], list) or not all(
            isinstance(item, str) for item in profile[field]
        ):
            raise ValueError(f"User profile field {field} must be a string list.")
    if not isinstance(profile["employment_type"]["allowed_types"], list):
        raise ValueError(
            "User profile field employment_type.allowed_types must be a list."
        )
    return profile


def load_user_profile(private_data_path: Path) -> dict:
    """Load user_profile.toml from the external private-data directory."""
    profile_path = Path(private_data_path) / PROFILE_FILENAME
    if not profile_path.is_file():
        raise FileNotFoundError(
            f"Private user profile not found: {profile_path}"
        )
    with profile_path.open("rb") as profile_file:
        profile = tomllib.load(profile_file)
    return validate_user_profile(profile)
