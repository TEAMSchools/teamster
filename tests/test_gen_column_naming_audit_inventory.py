"""Unit tests for scripts/gen_column_naming_audit_inventory.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "gen_column_naming_audit_inventory.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "gen_column_naming_audit_inventory", _SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_module_loads() -> None:
    module = _load_script()
    assert callable(module.main)


def test_flatten_description_collapses_internal_whitespace() -> None:
    module = _load_script()
    result = module._flatten_description("Student\n  date   of\tbirth.")
    assert result == "Student date of birth."


def test_flatten_description_strips_edges() -> None:
    module = _load_script()
    result = module._flatten_description("\n  hello world  \n")
    assert result == "hello world"


def test_flatten_description_handles_empty_and_none() -> None:
    module = _load_script()
    assert module._flatten_description("") == ""
    assert module._flatten_description(None) == ""


def test_domain_for_model_conformed() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_dates") == "Conformed"
    assert module._domain_for_model("dim_locations") == "Conformed"
    assert module._domain_for_model("dim_regions") == "Conformed"
    assert module._domain_for_model("dim_school_calendars") == "Conformed"
    assert module._domain_for_model("dim_terms") == "Conformed"


def test_domain_for_model_student() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_students") == "Student"
    assert module._domain_for_model("dim_student_enrollments") == "Student"
    assert module._domain_for_model("bridge_student_contacts") == "Student"
    assert module._domain_for_model("fct_student_attendance_daily") == "Attendance"


def test_domain_for_model_staff() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_staff") == "Staff"
    assert module._domain_for_model("dim_staff_work_assignments") == "Staff"
    assert module._domain_for_model("dim_staff_observation_types") == "Observation"
    assert module._domain_for_model("fct_staff_observations") == "Observation"


def test_domain_for_model_other_domains() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_assessments") == "Assessment"
    assert module._domain_for_model("dim_colleges") == "College"
    assert module._domain_for_model("fct_behavioral_incidents") == "Behavioral"
    assert module._domain_for_model("fct_family_communications") == "Behavioral"
    assert module._domain_for_model("fct_grades_term") == "Gradebook"
    assert module._domain_for_model("dim_surveys") == "Survey"
    assert module._domain_for_model("dim_job_postings") == "Talent"
    assert module._domain_for_model("dim_staffing_positions") == "Staffing"
    assert module._domain_for_model("fct_support_tickets") == "IT"


def test_domain_for_model_course() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_courses") == "Course"
    assert module._domain_for_model("dim_course_sections") == "Course"
    assert module._domain_for_model("bridge_course_section_teachers") == "Course"


def test_domain_for_model_unknown_returns_uncategorized() -> None:
    module = _load_script()
    assert module._domain_for_model("dim_wild_card_thing") == "Uncategorized"


def test_plumbing_columns_includes_dbt_source_relation() -> None:
    module = _load_script()
    assert "_dbt_source_relation" in module._plumbing_columns()


def test_plumbing_columns_returns_frozenset() -> None:
    module = _load_script()
    result = module._plumbing_columns()
    assert isinstance(result, frozenset)


def test_initial_rename_guess_student_number() -> None:
    module = _load_script()
    result = module._initial_rename_guess("student_number")
    assert result == ("local_student_identifier", "R1")


def test_initial_rename_guess_employee_number() -> None:
    module = _load_script()
    result = module._initial_rename_guess("employee_number")
    assert result == ("local_staff_identifier", "R2")


def test_initial_rename_guess_formatted_name() -> None:
    module = _load_script()
    result = module._initial_rename_guess("formatted_name")
    assert result == ("full_name", "R6")


def test_initial_rename_guess_unmapped_returns_none() -> None:
    module = _load_script()
    assert module._initial_rename_guess("student_key") is None
    assert module._initial_rename_guess("made_up_column") is None


def test_structural_additions_includes_mdcps() -> None:
    module = _load_script()
    rows = module._structural_additions()
    matches = [r for r in rows if r["proposed_name"] == "mdcps_student_identifier"]
    assert len(matches) == 1
    row = matches[0]
    assert row["domain"] == "Student"
    assert row["model"] == "dim_students"
    assert row["action"] == "add"
    assert row["rule_ref"] == "structural"
    assert row["current_column"] == ""
    assert row["review_status"] == "not_reviewed"


def test_structural_additions_includes_salesforce() -> None:
    module = _load_script()
    rows = module._structural_additions()
    assert any(
        r["proposed_name"] == "salesforce_contact_id" and r["model"] == "dim_students"
        for r in rows
    )


def test_structural_additions_includes_microsoft_365_email() -> None:
    module = _load_script()
    rows = module._structural_additions()
    assert any(
        r["proposed_name"] == "microsoft_365_email" and r["model"] == "dim_staff"
        for r in rows
    )


def test_structural_additions_all_have_required_keys() -> None:
    module = _load_script()
    required = {
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
    }
    for row in module._structural_additions():
        assert set(row.keys()) == required, f"keys differ for {row}"
