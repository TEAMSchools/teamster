from dagster import DynamicPartitionsDefinition

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.powerschool.enrollment.schema import (
    SUBMISSION_RECORD_SCHEMA,
)
from teamster.libraries.powerschool.enrollment.assets import (
    build_ps_enrollment_submission_records_asset,
)

PSE_PUBLISHED_ACTIONS_PARTITIONS_DEF = DynamicPartitionsDefinition(
    name=f"{CODE_LOCATION}__powerschool_enrollment__published_action_ids"
)

submission_records = build_ps_enrollment_submission_records_asset(
    code_location=CODE_LOCATION,
    partitions_def=PSE_PUBLISHED_ACTIONS_PARTITIONS_DEF,
    schema=SUBMISSION_RECORD_SCHEMA,
)

assets = [
    submission_records,
]
