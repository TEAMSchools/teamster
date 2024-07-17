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
universities_partitions_def_name = "overgrad__universities__id"


schools = build_overgrad_asset(asset_key=[*key_prefix, "schools"], schema=SCHOOL_SCHEMA)

students = build_overgrad_asset(
    asset_key=[*key_prefix, "students"], schema=STUDENT_SCHEMA
)

custom_fields = build_overgrad_asset(
    asset_key=[*key_prefix, "custom_fields"], schema=CUSTOM_FIELD_SCHEMA
)

admissions = build_overgrad_asset(
    asset_key=[*key_prefix, "admissions"],
    schema=ADMISSION_SCHEMA,
    universities_partitions_def_name=universities_partitions_def_name,
)

followings = build_overgrad_asset(
    asset_key=[*key_prefix, "followings"],
    schema=FOLLOWING_SCHEMA,
    universities_partitions_def_name=universities_partitions_def_name,
)

universities = build_overgrad_asset(
    asset_key=[*key_prefix, "universities"],
    schema=UNIVERSITY_SCHEMA,
    partitions_def=DynamicPartitionsDefinition(name=universities_partitions_def_name),
    auto_materialize_policy=AutoMaterializePolicy.eager(),
    deps=[admissions.key, followings.key],
)

assets = [
    admissions,
    custom_fields,
    followings,
    schools,
    students,
    universities,
]
