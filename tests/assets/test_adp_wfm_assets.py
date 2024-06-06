import random

from dagster import (
    AssetsDefinition,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    _check,
    instance_for_test,
    materialize,
)
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.adp.workforce_manager.assets import (
    accrual_reporting_period_summary,
    time_details,
)
from teamster.code_locations.kipptaf.resources import ADP_WORKFORCE_MANAGER_RESOURCE
from teamster.libraries.core.resources import get_io_manager_gcs_avro


def _test_asset(asset: AssetsDefinition):
    partitions_def = _check.inst(
        obj=asset.partitions_def, ttype=MultiPartitionsDefinition
    )
    date_partitions_def = partitions_def.get_partitions_def_for_dimension("date")

    with instance_for_test() as instance:
        if isinstance(date_partitions_def, DynamicPartitionsDefinition):
            instance.add_dynamic_partitions(
                partitions_def_name=_check.not_none(value=date_partitions_def.name),
                partition_keys=["foo"],
            )

            partition_keys = partitions_def.get_partition_keys(
                dynamic_partitions_store=instance
            )
        else:
            partition_keys = partitions_def.get_partition_keys()

        result = materialize(
            assets=[asset],
            instance=instance,
            partition_key=partition_keys[
                random.randint(a=0, b=(len(partition_keys) - 1))
            ],
            resources={
                "io_manager_gcs_avro": get_io_manager_gcs_avro(
                    code_location="test", test=True
                ),
                "adp_wfm": ADP_WORKFORCE_MANAGER_RESOURCE,
            },
        )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    step_materialization_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        step_materialization_data.materialization.metadata["records"].value, int
    )

    assert records > 0

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    assert asset_check_evaluation.passed

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_asset_adp_workforce_manager_accrual_reporting_period_summary():
    _test_asset(accrual_reporting_period_summary)


def test_asset_adp_workforce_manager_time_details():
    _test_asset(time_details)
