import random

from dagster import materialize

from teamster.core.resources import BIGQUERY_RESOURCE, get_io_manager_gcs_avro
from teamster.kipptaf.performance_management.assets import outlier_detection


def test_outlier_detection():
    partition_keys = outlier_detection.partitions_def.get_partition_keys()  # pyright: ignore[reportOptionalMemberAccess]

    partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    # partition_key="2023|PM3"

    result = materialize(
        assets=[outlier_detection],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("test"),
            "db_bigquery": BIGQUERY_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # pyright: ignore[reportOperatorIssue, reportAttributeAccessIssue, reportOptionalMemberAccess]
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""  # pyright: ignore[reportOptionalMemberAccess]
