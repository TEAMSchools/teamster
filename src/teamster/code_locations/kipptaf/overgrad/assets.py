from dagster import AutoMaterializePolicy, DynamicPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.overgrad.schema import (
    ADMISSION_SCHEMA,
    CUSTOM_FIELD_SCHEMA,
    FOLLOWING_SCHEMA,
    SCHOOL_SCHEMA,
    STUDENT_SCHEMA,
    UNIVERSITY_SCHEMA,
)
from teamster.libraries.overgrad.assets import build_overgrad_asset

key_prefix = [CODE_LOCATION, "overgrad"]

admissions = build_overgrad_asset(
    asset_key=[*key_prefix, "admissions"], schema=ADMISSION_SCHEMA
)

followings = build_overgrad_asset(
    asset_key=[*key_prefix, "followings"], schema=FOLLOWING_SCHEMA
)

schools = build_overgrad_asset(asset_key=[*key_prefix, "schools"], schema=SCHOOL_SCHEMA)

students = build_overgrad_asset(
    asset_key=[*key_prefix, "students"], schema=STUDENT_SCHEMA
)

custom_fields = build_overgrad_asset(
    asset_key=[*key_prefix, "custom_fields"], schema=CUSTOM_FIELD_SCHEMA
)

universities = build_overgrad_asset(
    asset_key=[*key_prefix, "universities"],
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
