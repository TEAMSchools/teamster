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
    assert "_dbt_source_relation" in module._PLUMBING_COLUMNS


def test_plumbing_columns_returns_frozenset() -> None:
    module = _load_script()
    assert isinstance(module._PLUMBING_COLUMNS, frozenset)


def test_initial_rename_guess_student_number() -> None:
    module = _load_script()
    result = module._initial_rename_guess("student_number")
    assert result == ("local_student_identifier", "R1")


def test_initial_rename_guess_employee_number() -> None:
    module = _load_script()
    result = module._initial_rename_guess("employee_number")
    assert result == ("local_staff_identifier", "R2")


def test_initial_rename_guess_powerschool_prefix() -> None:
    module = _load_script()
    result = module._initial_rename_guess("powerschool_school_id")
    assert result == ("sis_school_id", "R1")


def test_initial_rename_guess_unmapped_returns_none() -> None:
    module = _load_script()
    assert module._initial_rename_guess("student_key") is None
    assert module._initial_rename_guess("formatted_name") is None
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


def test_read_mart_yaml_applies_rename_guess() -> None:
    module = _load_script()
    rows = module._read_mart_yaml(_FIXTURE)
    by_name = {r["current_column"]: r for r in rows}
    sn = by_name["student_number"]
    assert sn["action"] == "rename"
    assert sn["proposed_name"] == "local_student_identifier"
    assert sn["rule_ref"] == "R1"


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
    assert all(r["reviewer_notes"] == "" for r in rows)


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


def test_load_edfi_extract() -> None:
    module = _load_script()
    csv_content = (
        "entity,attribute_camel,attribute_snake,description\n"
        "edFi_student,birthDate,birth_date,Date of birth.\n"
        "edFi_staff,birthDate,birth_date,Date of birth.\n"
        "edFi_student,firstName,first_name,First name.\n"
    )
    buf = io.StringIO(csv_content)
    result = module._load_edfi_extract(buf)
    assert "birth_date" in result
    assert len(result["birth_date"]) == 2
    assert "first_name" in result
    assert len(result["first_name"]) == 1


def _sample_edfi_dict() -> dict:
    return {
        "birth_date": [
            {
                "entity": "edFi_student",
                "attribute_camel": "birthDate",
                "description": "Date of birth.",
            },
            {
                "entity": "edFi_staff",
                "attribute_camel": "birthDate",
                "description": "Date of birth.",
            },
        ],
        "first_name": [
            {
                "entity": "edFi_student",
                "attribute_camel": "firstName",
                "description": "First name.",
            },
        ],
        "entry_date": [
            {
                "entity": "edFi_studentSchoolAssociation",
                "attribute_camel": "entryDate",
                "description": "The date on which an individual enters.",
            },
        ],
    }


def test_edfi_exact_match_found() -> None:
    module = _load_script()
    edfi = _sample_edfi_dict()
    result = module._edfi_exact_match("birth_date", edfi)
    assert result is not None
    proposed, note = result
    assert proposed == "birth_date"
    assert "edFi_student" in note
    assert "edFi_staff" in note


def test_edfi_exact_match_not_found() -> None:
    module = _load_script()
    edfi = _sample_edfi_dict()
    assert module._edfi_exact_match("student_key", edfi) is None


def test_edfi_fuzzy_match_above_threshold() -> None:
    module = _load_script()
    edfi = _sample_edfi_dict()
    result = module._edfi_fuzzy_match("entry_dates", edfi, threshold=0.6)
    assert result is not None
    assert "entry_date" in result


def test_edfi_fuzzy_match_below_threshold() -> None:
    module = _load_script()
    edfi = _sample_edfi_dict()
    result = module._edfi_fuzzy_match("completely_unrelated", edfi, threshold=0.6)
    assert result is None


def test_edfi_notes_appended_to_existing_rule() -> None:
    module = _load_script()
    edfi = {
        "employee_number": [
            {
                "entity": "edFi_staff",
                "attribute_camel": "staffUniqueId",
                "description": "A unique ID assigned to a staff.",
            },
        ],
    }
    row = {
        "action": "rename",
        "rule_ref": "R2",
        "proposed_name": "",
        "reviewer_notes": "KIPP-specific term: employee_number",
    }
    module._append_edfi_notes(row, "employee_number", edfi)
    assert "KIPP-specific term" in row["reviewer_notes"]
    assert "Ed-Fi" in row["reviewer_notes"]


def test_edfi_notes_not_appended_when_no_match() -> None:
    module = _load_script()
    edfi = {
        "birth_date": [
            {
                "entity": "edFi_student",
                "attribute_camel": "birthDate",
                "description": "DOB.",
            }
        ]
    }
    row = {"action": "keep", "rule_ref": "", "proposed_name": "", "reviewer_notes": ""}
    module._append_edfi_notes(row, "student_key", edfi)
    assert row["reviewer_notes"] == ""
