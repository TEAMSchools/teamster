import random

from dagster import _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.performance_management.assets import (
    observation_details,
)
from teamster.libraries.core.resources import SSH_COUCHDROP, get_io_manager_gcs_avro


def _test_asset(asset, partition_key=None):
    if partition_key is not None:
        pass
    elif asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "ssh_couchdrop": SSH_COUCHDROP,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]
    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    step_materialization_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        step_materialization_data.materialization.metadata["records"].value, int
    )

    assert records > 0

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_performance_management_observation_details_kipptaf():
    _test_asset(asset=observation_details, partition_key="2022|PM3")
