from dagster import AutoMaterializePolicy, DynamicPartitionsDefinition

from teamster.kipptaf.overgrad.schema import (
    ADMISSION_SCHEMA,
    CUSTOM_FIELD_SCHEMA,
    FOLLOWING_SCHEMA,
    SCHOOL_SCHEMA,
    STUDENT_SCHEMA,
    UNIVERSITY_SCHEMA,
)
from teamster.overgrad.assets import build_overgrad_asset

admissions = build_overgrad_asset(endpoint="admissions", schema=ADMISSION_SCHEMA)
followings = build_overgrad_asset(endpoint="followings", schema=FOLLOWING_SCHEMA)
schools = build_overgrad_asset(endpoint="schools", schema=SCHOOL_SCHEMA)
students = build_overgrad_asset(endpoint="students", schema=STUDENT_SCHEMA)
custom_fields = build_overgrad_asset(
    endpoint="custom_fields", schema=CUSTOM_FIELD_SCHEMA
)
universities = build_overgrad_asset(
    endpoint="universities",
    schema=UNIVERSITY_SCHEMA,
    partitions_def=DynamicPartitionsDefinition(name="overgrad__universities__id"),
    auto_materialize_policy=AutoMaterializePolicy.eager(),
)

assets = [
    admissions,
    custom_fields,
    followings,
    schools,
    students,
    universities,
]
