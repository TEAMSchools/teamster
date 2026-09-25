import json

import py_avro_schema

from teamster.libraries.cambium.schema import NJGPA

PAS_OPTIONS = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE


def _njgpa_avro_schema() -> dict:
    return json.loads(py_avro_schema.generate(py_type=NJGPA, options=PAS_OPTIONS))


def test_field_count():
    # 225 columns in the Cambium summative record file, plus the
    # source_file_name the SFTP factory appends to every row
    assert len(NJGPA.model_fields) == 226


def test_avro_schema_includes_load_bearing_fields():
    schema = _njgpa_avro_schema()

    top_level = {f["name"] for f in schema["fields"]}

    # every field the dbt staging model selects must survive generation —
    # py_avro_schema silently drops what it cannot represent, and the asset
    # check only compares top-level keys
    for field in [
        "source_file_name",
        "assessment_grade",
        "assessment_year",
        "grade_level_when_assessed",
        "local_student_identifier",
        "period",
        "state_student_identifier",
        "student_test_uuid",
        "student_with_disabilities",
        "subject",
        "summative_flag",
        "test_attemptedness_flag",
        "test_code",
        "test_performance_level",
        "test_scale_score",
        "test_status",
        "unit_1_online_test_start_date_time",
        "unit_4_online_test_start_date_time",
    ]:
        assert field in top_level, f"{field} missing from generated Avro schema"


def test_all_fields_are_nullable_strings():
    # the SFTP factory hands every CSV value through as a string or None, so a
    # non-string annotation would fail Avro validation at write time. Assert the
    # ANNOTATION, not just the default -- an `int | None = None` field would
    # satisfy a defaults-only check while still breaking at write time.
    for name, field in NJGPA.model_fields.items():
        assert field.default is None, f"{name} has a non-None default"
        assert field.annotation == (str | None), (
            f"{name} is annotated {field.annotation}, expected str | None"
        )
