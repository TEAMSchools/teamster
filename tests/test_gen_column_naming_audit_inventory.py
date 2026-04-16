"""Unit tests for scripts/gen_column_naming_audit_inventory.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import csv
import importlib.util
import io
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


def test_check_naming_rules_edfi_cognate() -> None:
    module = _load_script()
    result = module._check_naming_rules("student_number")
    assert result is not None
    rule_ref, note = result
    assert rule_ref == "R6"
    assert "Ed-Fi cognate" in note
    assert "local_student_identifier" in note


def test_check_naming_rules_source_prefix() -> None:
    module = _load_script()
    result = module._check_naming_rules("powerschool_school_id")
    assert result is not None
    rule_ref, note = result
    assert rule_ref == "R1"
    assert "source-system prefix" in note


def test_check_naming_rules_source_term() -> None:
    module = _load_script()
    result = module._check_naming_rules("sam_account_name")
    assert result is not None
    rule_ref, note = result
    assert rule_ref == "R1"
    assert "source-system term" in note


def test_check_naming_rules_kipp_term() -> None:
    module = _load_script()
    result = module._check_naming_rules("teacher_employee_number")
    assert result is not None
    rule_ref, note = result
    assert rule_ref == "R2"
    assert "KIPP-specific term" in note


def test_check_naming_rules_edfi_takes_priority_over_kipp() -> None:
    module = _load_script()
    # "employee_number" is both an Ed-Fi cognate AND contains a KIPP term.
    # R6 (Ed-Fi) should win because it's checked first.
    result = module._check_naming_rules("employee_number")
    assert result is not None
    rule_ref, _ = result
    assert rule_ref == "R6"


def test_check_naming_rules_internal_acronym() -> None:
    module = _load_script()
    result = module._check_naming_rules("sections_dcid")
    assert result is not None
    # sections_dcid is in _SOURCE_TERMS (R1) — R1 is checked before R7
    rule_ref, _ = result
    assert rule_ref == "R1"


def test_check_naming_rules_no_match() -> None:
    module = _load_script()
    assert module._check_naming_rules("student_key") is None
    assert module._check_naming_rules("birth_date") is None
    assert module._check_naming_rules("is_gifted") is None


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


_FIXTURE = _REPO_ROOT / "tests" / "fixtures" / "mart_yaml" / "dim_sample.yml"


def test_read_mart_yaml_emits_one_row_per_column() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    assert len(rows) == 4


def test_read_mart_yaml_sets_model_and_domain() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    assert all(r["model"] == "dim_sample" for r in rows)
    # dim_sample is unknown — falls through to Uncategorized
    assert all(r["domain"] == "Uncategorized" for r in rows)


def test_read_mart_yaml_flattens_description() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    assert by_name["sample_key"]["current_description"] == (
        "Surrogate key for sample. Spanning multiple lines."
    )


def test_read_mart_yaml_applies_plumbing_default() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    plumb = by_name["_dbt_source_relation"]
    assert plumb["action"] == "remove"
    assert plumb["rule_ref"] == "plumbing"
    assert plumb["proposed_name"] == ""


def test_read_mart_yaml_applies_naming_rules() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    sn = by_name["student_number"]
    assert sn["action"] == "rename"
    assert sn["proposed_name"] == ""
    assert sn["rule_ref"] == "R6"
    assert "Ed-Fi cognate" in sn["reviewer_notes"]


def test_read_mart_yaml_default_is_keep() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    ord_row = by_name["ordinary_column"]
    assert ord_row["action"] == "keep"
    assert ord_row["proposed_name"] == ""
    assert ord_row["rule_ref"] == ""


def test_read_mart_yaml_review_status_not_reviewed() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    assert all(r["review_status"] == "not_reviewed" for r in rows)


def test_write_csv_emits_header_and_rows() -> None:
    module = _load_script()
    rows = [
        {
            "domain": "Student",
            "model": "dim_students",
            "current_column": "student_number",
            "data_type": "int64",
            "current_description": "Local student ID.",
            "action": "rename",
            "proposed_name": "local_student_identifier",
            "rule_ref": "R1",
            "review_status": "not_reviewed",
            "reviewer_notes": "",
        }
    ]
    buf = io.StringIO()
    module._write_csv(rows, buf)
    buf.seek(0)
    reader = csv.DictReader(buf)
    header = reader.fieldnames
    assert header == [
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
    ]
    parsed = list(reader)
    assert len(parsed) == 1
    assert parsed[0]["proposed_name"] == "local_student_identifier"


def test_sort_rows_groups_by_domain_then_model() -> None:
    module = _load_script()
    unsorted = [
        {"domain": "Staff", "model": "dim_staff", "current_column": "a"},
        {"domain": "Student", "model": "dim_students", "current_column": "b"},
        {"domain": "Student", "model": "dim_students", "current_column": "a"},
        {"domain": "Conformed", "model": "dim_dates", "current_column": "c"},
    ]
    out = module._sort_rows(unsorted)
    assert [r["domain"] for r in out] == ["Conformed", "Staff", "Student", "Student"]
    # Within a model, preserve column order from the YAML (stable sort).
    student_rows = [r for r in out if r["domain"] == "Student"]
    assert [r["current_column"] for r in student_rows] == ["b", "a"]


_FIXTURE_R9 = (
    _REPO_ROOT / "tests" / "fixtures" / "mart_yaml" / "fct_sample_attendance.yml"
)


def test_read_mart_yaml_applies_r9_redundancy() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE_R9)
    by_name = {r["current_column"]: r for r in rows}
    ay = by_name["academic_year"]
    assert ay["action"] == "remove"
    assert ay["rule_ref"] == "R9"
    assert "reachable via" in ay["reviewer_notes"]


def test_read_mart_yaml_r9_does_not_flag_fk_columns() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE_R9)
    by_name = {r["current_column"]: r for r in rows}
    assert by_name["student_enrollment_key"]["action"] == "keep"
    assert by_name["attendance_key"]["action"] == "keep"


def test_read_mart_yaml_r9_student_number_on_fact() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE_R9)
    by_name = {r["current_column"]: r for r in rows}
    sn = by_name["student_number"]
    assert sn["action"] == "remove"
    assert sn["rule_ref"] == "R9"
