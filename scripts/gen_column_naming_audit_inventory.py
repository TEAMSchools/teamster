# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0"]
# ///

"""Generate the column naming audit inventory CSV.

Reads every YAML properties file under the kipptaf mart directories
(bridges/dimensions/facts) and emits one CSV row per (model, column) pair
plus pre-populated structural-addition rows for `dim_students` and
`dim_staff`.

Output: docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv

Usage:
    uv run scripts/gen_column_naming_audit_inventory.py

Design reference:
    docs/superpowers/specs/2026-04-15-column-naming-audit.md
"""

from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")


def _flatten_description(text: str | None) -> str:
    """Collapse whitespace runs to single spaces and strip edges."""
    if not text:
        return ""
    return _WS_RE.sub(" ", text).strip()


_DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    # (substring-in-model-name, domain). Order matters — first match wins.
    ("staff_observation", "Observation"),
    ("staff_attrition", "Staff"),
    ("staff_benefits", "Staff"),
    ("staff_membership", "Staff"),
    ("staff_status", "Staff"),
    ("staff_work_assignment", "Staff"),
    ("work_assignment", "Staff"),
    ("staffing", "Staffing"),
    ("student_attendance", "Attendance"),
    ("student_contact", "Student"),
    ("student_section_enrollment", "Student"),
    ("student_enrollment", "Student"),
    ("student_assessment_expectation", "Assessment"),
    ("behavioral", "Behavioral"),
    ("family_communication", "Behavioral"),
    ("grade", "Gradebook"),
    ("assessment", "Assessment"),
    ("college", "College"),
    ("survey", "Survey"),
    ("course", "Course"),
    ("job_candidate", "Talent"),
    ("job_posting", "Talent"),
    ("support_ticket", "IT"),
    ("student", "Student"),
    ("staff", "Staff"),
)

_CONFORMED_MODELS = frozenset(
    [
        "dim_dates",
        "dim_locations",
        "dim_regions",
        "dim_school_calendars",
        "dim_terms",
    ]
)


def _domain_for_model(model_name: str) -> str:
    """Classify a mart model name into an audit-review domain."""
    if model_name in _CONFORMED_MODELS:
        return "Conformed"
    for substring, domain in _DOMAIN_RULES:
        if substring in model_name:
            return domain
    return "Uncategorized"


_PLUMBING_COLUMNS: frozenset[str] = frozenset(
    [
        "_dbt_source_relation",
    ]
)


def _plumbing_columns() -> frozenset[str]:
    """Columns whose default audit action is 'remove' (plumbing)."""
    return _PLUMBING_COLUMNS


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
