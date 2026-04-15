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

import csv
import re
from pathlib import Path
from typing import TextIO

import yaml

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


# Pre-populated rename guesses carried over from the original 67-column
# audit. Each entry is (current_name, (proposed_name, rule_ref)). The rule
# references the rubric section in
# docs/superpowers/specs/2026-04-15-column-naming-audit.md.
_RENAME_GUESSES: dict[str, tuple[str, str]] = {
    # Rule 1 — strip source-system names (student identifier)
    "student_number": ("local_student_identifier", "R1"),
    # Rule 2 — no KIPP-specific language (staff identifier)
    "employee_number": ("local_staff_identifier", "R2"),
    "teacher_employee_number": ("teacher_staff_identifier", "R2"),
    "observer_employee_number": ("observer_staff_identifier", "R2"),
    "teammate_employee_number": ("teammate_staff_identifier", "R2"),
    "recruiter_employee_number": ("recruiter_staff_identifier", "R2"),
    # Rule 6 — Ed-Fi / plain English for person names
    "formatted_name": ("full_name", "R6"),
    "family_name_1": ("last_name", "R6"),
    "given_name": ("first_name", "R6"),
    "manager_formatted_name": ("manager_full_name", "R6"),
    "manager_family_name_1": ("manager_last_name", "R6"),
    "manager_given_name": ("manager_first_name", "R6"),
    # Rule 1 — PowerSchool identifier stripping
    "powerschool_school_id": ("sis_school_id", "R1"),
    "deanslist_school_id": ("behavior_system_school_id", "R1"),
    "powerschool_term_id": ("sis_term_id", "R1"),
    "powerschool_year_id": ("sis_year_id", "R1"),
    "powerschool_person_id": ("contact_person_id", "R1"),
    "sections_dcid": ("section_id", "R1"),
    "teachernumber": ("teacher_number", "R1"),
}


def _initial_rename_guess(column_name: str) -> tuple[str, str] | None:
    """Return (proposed_name, rule_ref) for known renames, else None."""
    return _RENAME_GUESSES.get(column_name)


def _structural_additions() -> list[dict[str, str]]:
    """Pre-populated add-rows for structural columns defined in the spec."""
    template = {
        "current_column": "",
        "current_description": "",
        "action": "add",
        "rule_ref": "structural",
        "review_status": "not_reviewed",
        "reviewer_notes": "",
    }
    return [
        {
            **template,
            "domain": "Student",
            "model": "dim_students",
            "data_type": "string",
            "proposed_name": "mdcps_student_identifier",
        },
        {
            **template,
            "domain": "Student",
            "model": "dim_students",
            "data_type": "string",
            "proposed_name": "salesforce_contact_id",
        },
        {
            **template,
            "domain": "Staff",
            "model": "dim_staff",
            "data_type": "string",
            "proposed_name": "microsoft_365_email",
        },
    ]


def _read_mart_yaml(path: Path) -> list[dict[str, str]]:
    """Parse a single mart properties YAML into audit-row dicts."""
    with path.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)

    plumbing = _plumbing_columns()
    rows: list[dict[str, str]] = []

    for model in doc.get("models", []) or []:
        model_name = model["name"]
        domain = _domain_for_model(model_name)
        for column in model.get("columns", []) or []:
            col_name = column["name"]
            row: dict[str, str] = {
                "domain": domain,
                "model": model_name,
                "current_column": col_name,
                "data_type": column.get("data_type", "") or "",
                "current_description": _flatten_description(column.get("description")),
                "action": "keep",
                "proposed_name": "",
                "rule_ref": "",
                "review_status": "not_reviewed",
                "reviewer_notes": "",
            }

            if col_name in plumbing:
                row["action"] = "remove"
                row["rule_ref"] = "plumbing"
            else:
                guess = _initial_rename_guess(col_name)
                if guess is not None:
                    proposed, rule_ref = guess
                    row["action"] = "rename"
                    row["proposed_name"] = proposed
                    row["rule_ref"] = rule_ref

            rows.append(row)

    return rows


CSV_FIELDS: tuple[str, ...] = (
    "domain",
    "model",
    "current_column",
    "data_type",
    "current_description",
    "action",
    "proposed_name",
    "rule_ref",
    "review_status",
    "reviewer_notes",
)

MART_YAML_DIRS: tuple[Path, ...] = (
    Path("src/dbt/kipptaf/models/marts/bridges/properties"),
    Path("src/dbt/kipptaf/models/marts/dimensions/properties"),
    Path("src/dbt/kipptaf/models/marts/facts/properties"),
)

OUTPUT_CSV = Path("docs/superpowers/specs/2026-04-15-column-naming-audit-inventory.csv")


def _sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Stable sort by (domain, model). Within a model, YAML order is kept."""
    return sorted(rows, key=lambda r: (r["domain"], r["model"]))


def _write_csv(rows: list[dict[str, str]], fh: TextIO) -> None:
    writer = csv.DictWriter(fh, fieldnames=list(CSV_FIELDS))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_FIELDS})


def main() -> None:
    rows: list[dict[str, str]] = []
    for directory in MART_YAML_DIRS:
        for yaml_path in sorted(directory.glob("*.yml")):
            rows.extend(_read_mart_yaml(yaml_path))
    rows.extend(_structural_additions())
    sorted_rows = _sort_rows(rows)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fh:
        _write_csv(sorted_rows, fh)

    print(f"Wrote {len(sorted_rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
