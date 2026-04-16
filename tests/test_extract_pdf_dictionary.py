"""Unit tests for scripts/extract_pdf_dictionary.py.

The script filename uses underscores specifically so we can import it.
We use importlib.util rather than changing project-wide pytest config,
keeping the import pattern local to this test file.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "extract_pdf_dictionary.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("extract_pdf_dictionary", _SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_script_module_loads() -> None:
    module = _load_script()
    assert callable(module.main)


class TestPascalToSnake:
    def test_simple(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("StudentNumber") == "student_number"

    def test_all_caps_short(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("ID") == "id"

    def test_mixed_caps_and_pascal(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("DCid") == "dcid"

    def test_consecutive_caps(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("SSN") == "ssn"

    def test_single_word(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("Gender") == "gender"

    def test_already_lowercase(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("schoolid") == "schoolid"

    def test_underscore_preserved(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("Alert_Discipline") == "alert_discipline"

    def test_trailing_caps(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("StudentID") == "student_id"

    def test_complex_mixed(self) -> None:
        module = _load_script()
        assert module.pascal_to_snake("GPAPoints") == "gpa_points"

    def test_s_nj_prefix(self) -> None:
        """Extension table names like S_NJ_STU_X stay lowercase."""
        module = _load_script()
        assert module.pascal_to_snake("s_nj_stu_x") == "s_nj_stu_x"


class TestCamelToSnake:
    def test_simple(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("birthDate") == "birth_date"

    def test_single_word(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("person") == "person"

    def test_multi_segment(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("genderCode") == "gender_code"

    def test_consecutive_upper(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("emailURI") == "email_uri"

    def test_already_snake(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("birth_date") == "birth_date"

    def test_code_value(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("codeValue") == "code_value"

    def test_long_camel(self) -> None:
        module = _load_script()
        assert (
            module.camel_to_snake("countrySubdivisionLevel1")
            == "country_subdivision_level_1"
        )

    def test_formatted_name(self) -> None:
        module = _load_script()
        assert module.camel_to_snake("formattedName") == "formatted_name"


class TestClassifyPii:
    """Test the PII heuristic classifier."""

    def test_name_columns_are_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("first_name", "") is True
        assert module.classify_pii("last_name", "") is True
        assert module.classify_pii("middle_name", "") is True
        assert module.classify_pii("formatted_name", "") is True
        assert module.classify_pii("family_name_1", "") is True
        assert module.classify_pii("given_name", "") is True
        assert module.classify_pii("nick_name", "") is True
        assert module.classify_pii("lastfirst", "") is True

    def test_dob_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("dob", "") is True
        assert module.classify_pii("birth_date", "") is True
        assert module.classify_pii("person__birth_date", "") is True

    def test_ssn_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("ssn", "") is True
        assert module.classify_pii("social_security", "") is True

    def test_address_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("street", "") is True
        assert module.classify_pii("city", "") is True
        assert module.classify_pii("zip", "") is True
        assert module.classify_pii("postal_code", "") is True
        assert module.classify_pii("line_one", "Legal address line one.") is True
        assert module.classify_pii("city_name", "") is True

    def test_phone_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("home_phone", "") is True
        assert module.classify_pii("dial_number", "") is True
        assert module.classify_pii("guardianfax", "") is True

    def test_email_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("guardianemail", "") is True
        assert module.classify_pii("email_uri", "") is True

    def test_description_keyword_triggers_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("some_field", "Social Security Number") is True
        assert (
            module.classify_pii("some_field", "Date of birth for the student") is True
        )
        assert module.classify_pii("some_field", "Home address of the worker") is True
        assert (
            module.classify_pii("some_field", "Emergency contact phone number") is True
        )

    def test_non_pii_columns(self) -> None:
        module = _load_script()
        assert module.classify_pii("schoolid", "") is False
        assert module.classify_pii("grade_level", "") is False
        assert module.classify_pii("entrydate", "") is False
        assert module.classify_pii("termid", "") is False
        assert module.classify_pii("code_value", "") is False
        assert module.classify_pii("effective_date", "") is False

    def test_government_id_is_pii(self) -> None:
        module = _load_script()
        assert module.classify_pii("state_studentnumber", "") is True
        assert module.classify_pii("web_password", "") is True

    def test_emergency_contact_is_pii(self) -> None:
        module = _load_script()
        assert (
            module.classify_pii("emerg_contact_1", "Emergency contact information.")
            is True
        )


# Representative text blocks extracted from real PowerSchool PDF pages.
# These are minimal fixtures -- not full pages.

PS_FIXTURE_PAGE_WITH_HEADER = """\
736
This table maintains Student demographics and other School related information such as Lunch ID, Grade Level and scheduling data.
Column Name InitialVersion Data Type Description
Alert_Discipline 3.6.1 CLOB One of many various alerts in PowerSchool. This field stores the text tied to the alert.
Alert_DisciplineExpires 3.6.1 Date An expiration date for the Discipline alert.
StudentNumber 3.6.1 Number(10,0) The student's assigned number.
Students, 167 (ver3.6.1)
PowerSchool Private Information \u2013 Confidential
"""

PS_FIXTURE_PAGE_CONTINUATION = """\
737
SSN 3.6.1 Varchar2(12) Social security number. Masked by default.
FedEthnicity 5.0.3 Number(10,0) Federal ethnicity code.
Mailing_Street 3.6.1 Varchar2(70) Mailing street address.
Students, 167 (ver3.6.1)
PowerSchool Private Information \u2013 Confidential
"""

PS_FIXTURE_NEW_TABLE = """\
800
This table contains CC (Current Class) data.
Column Name InitialVersion Data Type Description
StudentID 3.6.1 Number(10,0) Links to students table.
SectionID 3.6.1 Number(10,0) Links to sections table.
DateEnrolled 3.6.1 Date Date enrolled into section.
CC (ver3.6.1)
"""

PS_FIXTURE_TABLE_WITH_COUNT = """\
50
AssignmentSectionID 3.6.1 Number(10,0) Related assignment section.
Points 3.6.1 Number(10,0) Points earned.
AssignmentScore, 2 (ver3.6.1)
PowerSchool Private Information \u2013 Confidential
"""


class TestPsTableNameExtractor:
    """Test extracting the table name from a page's footer-style header."""

    def test_extracts_table_with_count(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name(PS_FIXTURE_PAGE_WITH_HEADER)
        assert result == "Students"

    def test_extracts_table_without_count(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name(PS_FIXTURE_NEW_TABLE)
        assert result == "CC"

    def test_extracts_table_from_score_page(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name(PS_FIXTURE_TABLE_WITH_COUNT)
        assert result == "AssignmentScore"

    def test_returns_none_for_no_header(self) -> None:
        module = _load_script()
        result = module.extract_ps_table_name("Some random text\nwithout headers\n")
        assert result is None


class TestPsColumnParser:
    """Test parsing individual column lines from PS PDF text."""

    def test_parses_simple_column(self) -> None:
        module = _load_script()
        text = "StudentNumber 3.6.1 Number(10,0) The student's assigned number."
        entries = module.parse_ps_columns(text)
        assert len(entries) == 1
        assert entries[0]["source_column"] == "StudentNumber"
        assert entries[0]["description"] == "The student's assigned number."

    def test_parses_multiple_columns(self) -> None:
        module = _load_script()
        text = (
            "Alert_Discipline 3.6.1 CLOB "
            "One of many various alerts in PowerSchool. "
            "This field stores the text tied to the alert.\n"
            "StudentNumber 3.6.1 Number(10,0) "
            "The student's assigned number.\n"
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 2
        assert entries[0]["source_column"] == "Alert_Discipline"
        assert entries[1]["source_column"] == "StudentNumber"

    def test_skips_header_line(self) -> None:
        module = _load_script()
        text = (
            "Column Name InitialVersion Data Type Description\n"
            "StudentNumber 3.6.1 Number(10,0) The student's assigned number."
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 1
        assert entries[0]["source_column"] == "StudentNumber"

    def test_skips_page_number_and_footer(self) -> None:
        module = _load_script()
        text = (
            "736\n"
            "StudentNumber 3.6.1 Number(10,0) The student's assigned number.\n"
            "Students, 167 (ver3.6.1)\n"
            "PowerSchool Private Information \u2013 Confidential\n"
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 1
        assert entries[0]["source_column"] == "StudentNumber"

    def test_various_data_types(self) -> None:
        module = _load_script()
        text = (
            "Alert_Discipline 3.6.1 CLOB Alert text.\n"
            "FedEthnicity 5.0.3 Number(10,0) Federal ethnicity.\n"
            "SSN 3.6.1 Varchar2(12) Social security number.\n"
            "DOB 3.6.1 Date Date of birth.\n"
        )
        entries = module.parse_ps_columns(text)
        assert len(entries) == 4
        assert entries[0]["source_column"] == "Alert_Discipline"
        assert entries[2]["source_column"] == "SSN"

    def test_clob_description_extracted(self) -> None:
        module = _load_script()
        text = "Alert_Discipline 3.6.1 CLOB One of many various alerts."
        entries = module.parse_ps_columns(text)
        assert entries[0]["description"] == "One of many various alerts."


class TestPsTableToModelName:
    """Test converting PDF table names to dbt model names."""

    def test_simple_table(self) -> None:
        module = _load_script()
        assert module.ps_table_to_model_name("Students") == "stg_powerschool__students"

    def test_mixed_case(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("StoredGrades")
            == "stg_powerschool__storedgrades"
        )

    def test_short_name(self) -> None:
        module = _load_script()
        assert module.ps_table_to_model_name("CC") == "stg_powerschool__cc"

    def test_extension_table(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("S_NJ_STU_X") == "stg_powerschool__s_nj_stu_x"
        )

    def test_camel_compound(self) -> None:
        module = _load_script()
        assert (
            module.ps_table_to_model_name("AssignmentScore")
            == "stg_powerschool__assignmentscore"
        )

    def test_person_table(self) -> None:
        module = _load_script()
        assert module.ps_table_to_model_name("Person") == "stg_powerschool__person"


class TestBuildPsYamlIndex:
    """Test building the YAML column lookup index."""

    def test_index_contains_students_columns(self) -> None:
        module = _load_script()
        index = module.build_ps_yaml_index()
        # stg_powerschool__students.yml exists and has columns
        assert "stg_powerschool__students" in index
        columns = index["stg_powerschool__students"]
        assert "first_name" in columns
        assert "student_number" not in columns or "id" in columns
        # Verify it's a set
        assert isinstance(columns, set)

    def test_index_contains_cc_columns(self) -> None:
        module = _load_script()
        index = module.build_ps_yaml_index()
        assert "stg_powerschool__cc" in index
        columns = index["stg_powerschool__cc"]
        assert "studentid" in columns or "dcid" in columns


import json


class TestBuildPsMapping:
    """Test the PowerSchool PDF-to-JSON mapping builder."""

    def test_mapping_structure_from_fixture_pages(self) -> None:
        module = _load_script()
        # Simulate extracted pages
        pages = [PS_FIXTURE_PAGE_WITH_HEADER, PS_FIXTURE_PAGE_CONTINUATION]
        yaml_index = {
            "stg_powerschool__students": {
                "alert_discipline",
                "alert_disciplineexpires",
                "student_number",
                "ssn",
                "fedethnicity",
                "mailing_street",
            },
        }
        result = module.build_ps_mapping(pages, yaml_index)

        assert result["source"] == "powerschool"
        assert "extracted_at" in result
        assert "stats" in result
        assert "entries" in result
        assert "unmatched_pdf" in result
        assert "unmatched_yaml" in result

        # Check that matched entries exist
        matched_cols = {e["column"] for e in result["entries"]}
        assert "student_number" in matched_cols
        assert "alert_discipline" in matched_cols

    def test_pii_classification_in_mapping(self) -> None:
        module = _load_script()
        pages = [PS_FIXTURE_PAGE_WITH_HEADER, PS_FIXTURE_PAGE_CONTINUATION]
        yaml_index = {
            "stg_powerschool__students": {
                "alert_discipline",
                "student_number",
                "ssn",
                "mailing_street",
            },
        }
        result = module.build_ps_mapping(pages, yaml_index)

        entries_by_col = {e["column"]: e for e in result["entries"]}
        # SSN should be PII
        if "ssn" in entries_by_col:
            assert entries_by_col["ssn"]["contains_pii"] is True
        # alert_discipline should not be PII
        if "alert_discipline" in entries_by_col:
            assert entries_by_col["alert_discipline"]["contains_pii"] is False
        # mailing_street should be PII
        if "mailing_street" in entries_by_col:
            assert entries_by_col["mailing_street"]["contains_pii"] is True

    def test_stats_counts(self) -> None:
        module = _load_script()
        pages = [PS_FIXTURE_PAGE_WITH_HEADER]
        yaml_index = {
            "stg_powerschool__students": {
                "alert_discipline",
                "student_number",
            },
        }
        result = module.build_ps_mapping(pages, yaml_index)
        stats = result["stats"]
        assert stats["matched"] > 0
        assert isinstance(stats["pdf_entries"], int)
        assert isinstance(stats["unmatched_pdf"], int)


# Representative text blocks extracted from real ADP PDF pages.

ADP_FIXTURE_PAGE = """\
/workers/person/birthDate Birth Date Masked by default. Y
/workers/person/raceCode Race Y
/workers/person/genderCode Gender Y
/workers/person/communication/emails/emailUri Personal Email Y
/workers/person/legalAddress/postalCode Postal Code Y
/workers/workerDates/originalHireDate Original Hire Date Y
/workers/workerDates/terminationDate Termination Date Y
"""

ADP_FIXTURE_PAGE_2 = """\
/workers/person/legalName/givenName Legal First Name Y
/workers/person/legalName/familyName1 Legal Last Name Y
/workers/person/legalName/formattedName Legal Full Name Y
/workers/person/preferredName/givenName Preferred First Name Y
/workers/person/highestEducationLevelCode Highest Education Level Y
/workers/workerID/idValue Worker ID Y
"""

ADP_FIXTURE_WITH_NA = """\
/workers/person/disabledIndicator Disabled Indicator NA
/workers/customFieldGroup/codeFields Custom Code Fields Y
"""


class TestAdpPathParser:
    """Test extracting ADP schema location + field name from PDF text."""

    def test_parses_simple_paths(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        assert len(entries) >= 5

        paths = {e["schema_path"] for e in entries}
        assert "/workers/person/birthDate" in paths
        assert "/workers/person/communication/emails/emailUri" in paths

    def test_extracts_field_name(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        by_path = {e["schema_path"]: e for e in entries}
        assert by_path["/workers/person/birthDate"]["field_name"] == "Birth Date"

    def test_extracts_description_with_note(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        by_path = {e["schema_path"]: e for e in entries}
        birth = by_path["/workers/person/birthDate"]
        assert "Masked by default" in birth["description"]

    def test_field_name_only_no_note(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_PAGE)
        by_path = {e["schema_path"]: e for e in entries}
        race = by_path["/workers/person/raceCode"]
        assert race["field_name"] == "Race"
        # Description should be just the field name when no note
        assert race["description"] == "Race"

    def test_na_entries_included(self) -> None:
        module = _load_script()
        entries = module.parse_adp_entries(ADP_FIXTURE_WITH_NA)
        assert len(entries) >= 1
        paths = {e["schema_path"] for e in entries}
        assert "/workers/person/disabledIndicator" in paths


class TestAdpPathToColumn:
    """Test converting ADP JSON paths to staging YAML column names."""

    def test_simple_path(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/person/birthDate")
            == "person__birth_date"
        )

    def test_nested_path(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/person/legalName/givenName")
            == "person__legal_name__given_name"
        )

    def test_worker_dates(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/workerDates/originalHireDate")
            == "worker_dates__original_hire_date"
        )

    def test_worker_id(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/workerID/idValue")
            == "worker_id__id_value"
        )

    def test_deep_nested(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column(
                "/workers/person/legalAddress/countrySubdivisionLevel1"
            )
            == "person__legal_address__country_subdivision_level_1"
        )

    def test_communication_emails(self) -> None:
        module = _load_script()
        assert (
            module.adp_path_to_column("/workers/person/communication/emails/emailUri")
            == "person__communication__emails__email_uri"
        )


class TestBuildAdpYamlIndex:
    """Test building the ADP YAML column lookup index."""

    def test_index_contains_workers(self) -> None:
        module = _load_script()
        index = module.build_adp_yaml_index()
        assert "stg_adp_workforce_now__workers" in index

    def test_workers_has_scalar_columns(self) -> None:
        module = _load_script()
        index = module.build_adp_yaml_index()
        workers = index["stg_adp_workforce_now__workers"]
        # These are scalar columns that should be in the index
        assert "person__birth_date" in workers["columns"]
        assert "associate_oid" in workers["columns"]

    def test_array_struct_columns_flagged(self) -> None:
        module = _load_script()
        index = module.build_adp_yaml_index()
        workers = index["stg_adp_workforce_now__workers"]
        # ARRAY<STRUCT<...>> columns should be in skip set
        assert "work_assignments" in workers["skip_columns"]
        assert "photos" in workers["skip_columns"]
