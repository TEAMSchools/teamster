# import random

from dagster import materialize

from teamster.core.resources import BIGQUERY_RESOURCE, get_io_manager_gcs_avro
from teamster.kipptaf.performance_management.assets import outlier_detection


def test_outlier_detection():
    # partition_keys = outlier_detection.partitions_def.get_partition_keys()

    result = materialize(
        assets=[outlier_detection],
        partition_key="2023|PM2",
        # partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "db_bigquery": BIGQUERY_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
        .value
        > 0
    )
