import random

from dagster import materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.adp.workforce_now.api.assets import workers
from teamster.kipptaf.resources import ADP_WORKFORCE_NOW_RESOURCE


def test_adp_wfn_asset():
    partition_keys = workers.partitions_def.get_partition_keys()

    result = materialize(
        assets=[workers],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "adp_wfn": ADP_WORKFORCE_NOW_RESOURCE,
        },
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["record_count"]  # type: ignore
        .value
        > 0
    )
