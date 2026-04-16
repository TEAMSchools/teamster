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
