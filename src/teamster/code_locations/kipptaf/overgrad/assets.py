from dagster import AssetKey, AutomationCondition, DynamicPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.overgrad.schema import UNIVERSITY_SCHEMA
from teamster.libraries.overgrad.assets import build_overgrad_asset

universities = build_overgrad_asset(
    code_location=CODE_LOCATION,
    name="universities",
    schema=UNIVERSITY_SCHEMA,
    partitions_def=DynamicPartitionsDefinition(name="overgrad__universities__id"),
    automation_condition=(
        AutomationCondition.missing()
        & ~AutomationCondition.in_progress()
        & ~AutomationCondition.any_deps_match(AutomationCondition.in_progress())
    ),
    deps=[
        AssetKey(["kippcamden", "overgrad", "admissions"]),
        AssetKey(["kippcamden", "overgrad", "followings"]),
        AssetKey(["kippnewark", "overgrad", "admissions"]),
        AssetKey(["kippnewark", "overgrad", "followings"]),
    ],
)

assets = [
    universities,
]
