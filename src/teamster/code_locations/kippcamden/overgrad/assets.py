from teamster.code_locations.kippcamden import CODE_LOCATION
from teamster.code_locations.kippcamden.overgrad.schema import (
    ADMISSION_SCHEMA,
    CUSTOM_FIELD_SCHEMA,
    FOLLOWING_SCHEMA,
    SCHOOL_SCHEMA,
    STUDENT_SCHEMA,
)
from teamster.libraries.overgrad.assets import build_overgrad_asset

schools = build_overgrad_asset(
    code_location=CODE_LOCATION, name="schools", schema=SCHOOL_SCHEMA
)

students = build_overgrad_asset(
    code_location=CODE_LOCATION, name="students", schema=STUDENT_SCHEMA
)

custom_fields = build_overgrad_asset(
    code_location=CODE_LOCATION, name="custom_fields", schema=CUSTOM_FIELD_SCHEMA
)

admissions = build_overgrad_asset(
    code_location=CODE_LOCATION, name="admissions", schema=ADMISSION_SCHEMA
)

followings = build_overgrad_asset(
    code_location=CODE_LOCATION, name="followings", schema=FOLLOWING_SCHEMA
)

assets = [
    admissions,
    custom_fields,
    followings,
    schools,
    students,
]
