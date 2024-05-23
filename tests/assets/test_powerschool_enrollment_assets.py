import random

from dagster import AssetsDefinition, EnvVar, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.powerschool.enrollment.assets import submission_records
from teamster.powerschool.enrollment.resources import PowerSchoolEnrollmentResource


def _test_asset(asset: AssetsDefinition, partition_key=None):
    if asset.partitions_def is not None and partition_key is None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "ps_enrollment": PowerSchoolEnrollmentResource(
                api_key=EnvVar("PS_ENROLLMENT_API_KEY"), page_size=1000
            ),
        },
        partition_key=partition_key,
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # pyright: ignore[reportOperatorIssue, reportAttributeAccessIssue, reportOptionalMemberAccess]
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""  # pyright: ignore[reportOptionalMemberAccess]


def test_submission_records():
    _test_asset(asset=submission_records)
