from dagster import (
    DynamicPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    build_schedule_from_partitioned_job,
    schedule,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_manager.assets import (
    adp_wfm_assets_dynamic,
)
from teamster.code_locations.kipptaf.adp.workforce_manager.jobs import (
    adp_wfm_daily_partition_asset_job,
    adp_wfm_dynamic_partition_asset_job,
)
from teamster.libraries.adp.workforce_manager.resources import (
    AdpWorkforceManagerResource,
)

adp_wfm_daily_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=adp_wfm_daily_partition_asset_job, hour_of_day=23, minute_of_hour=50
)


@schedule(
    cron_schedule="50 23 * * *",
    name=f"{CODE_LOCATION}_adp_wfm_dynamic_partition_schedule",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=adp_wfm_dynamic_partition_asset_job,
)
def adp_wfm_dynamic_partition_schedule(
    context: ScheduleEvaluationContext, adp_wfm: AdpWorkforceManagerResource
):
    for asset in adp_wfm_assets_dynamic:
        partitions_def = _check.inst(asset.partitions_def, MultiPartitionsDefinition)

        symbolic_id_partition = partitions_def.get_partitions_def_for_dimension(
            "symbolic_id"
        )
        date_partition = _check.inst(
            partitions_def.get_partitions_def_for_dimension("date"),
            DynamicPartitionsDefinition,
        )

        for symbolic_id in symbolic_id_partition.get_partition_keys():
            symbolic_period_response = _check.not_none(
                adp_wfm.post(
                    endpoint="v1/commons/symbolicperiod/read",
                    json={
                        "where": {"currentUser": True, "symbolicPeriodId": symbolic_id}
                    },
                )
            )

            symbolic_period_record = symbolic_period_response.json()

            partition_key = MultiPartitionKey(
                {"symbolic_id": symbolic_id, "date": symbolic_period_record["begin"]}
            )

            context.instance.add_dynamic_partitions(
                partitions_def_name=_check.not_none(value=date_partition.name),
                partition_keys=[symbolic_period_record["begin"]],
            )

            yield RunRequest(
                run_key=f"{asset.key.to_python_identifier()}_{partition_key}",
                asset_selection=[asset.key],
                partition_key=partition_key,
            )


schedules = [
    adp_wfm_daily_partition_asset_job_schedule,
    adp_wfm_dynamic_partition_schedule,
]
