import random

from dagster import (
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    instance_for_test,
    materialize,
)

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.adp.workforce_manager.assets import build_adp_wfm_asset
from teamster.kipptaf.resources import ADP_WORKFORCE_MANAGER_RESOURCE
from teamster.staging import LOCAL_TIMEZONE


def _test_asset(asset_name, report_name, hyperfind, symbolic_ids, date_partitions_def):
    asset = build_adp_wfm_asset(
        asset_name=asset_name,
        report_name=report_name,
        hyperfind=hyperfind,
        symbolic_ids=symbolic_ids,
        date_partitions_def=date_partitions_def,
    )

    with instance_for_test() as instance:
        if isinstance(date_partitions_def, DynamicPartitionsDefinition):
            instance.add_dynamic_partitions(
                partitions_def_name=date_partitions_def.name, partition_keys=["foo"]
            )

            partition_keys = asset.partitions_def.get_partition_keys(
                dynamic_partitions_store=instance
            )
        else:
            partition_keys = asset.partitions_def.get_partition_keys()

        result = materialize(
            assets=[asset],
            instance=instance,
            partition_key=partition_keys[
                random.randint(a=0, b=(len(partition_keys) - 1))
            ],
            resources={
                "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
                "adp_wfm": ADP_WORKFORCE_MANAGER_RESOURCE,
            },
        )

    assert result.success

    event = result.get_asset_materialization_events()[0]

    assert event.event_specific_data.materialization.metadata["records"].value > 0


def test_asset_adp_workforce_manager_accrual_reporting_period_summary():
    _test_asset(
        asset_name="accrual_reporting_period_summary",
        report_name="AccrualReportingPeriodSummary",
        hyperfind="All Home",
        symbolic_ids=["Previous_SchedPeriod", "Current_SchedPeriod"],
        date_partitions_def=DailyPartitionsDefinition(
            start_date="2023-05-17",
            timezone=LOCAL_TIMEZONE.name,
            fmt="%Y-%m-%d",
            end_offset=1,
        ),
    )


def test_asset_adp_workforce_manager_time_details():
    _test_asset(
        asset_name="time_details",
        report_name="TimeDetails",
        hyperfind="All Home",
        symbolic_ids=["Previous_SchedPeriod", "Current_SchedPeriod"],
        date_partitions_def=DynamicPartitionsDefinition(
            name="staging__adp_workforce_manager__time_details_date"
        ),
    )
