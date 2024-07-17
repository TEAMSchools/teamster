from typing import Generator

from dagster import (
    DynamicPartitionsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    _check,
    build_schedule_from_partitioned_job,
    define_asset_job,
    schedule,
)

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.adp.workforce_manager.assets import (
    adp_wfm_assets_daily,
    adp_wfm_assets_dynamic,
)
from teamster.libraries.adp.workforce_manager.resources import (
    AdpWorkforceManagerResource,
)

adp_wfm_daily_partition_asset_job_schedule = build_schedule_from_partitioned_job(
    job=define_asset_job(
        name=f"{CODE_LOCATION}_adp_wfm_daily_partition_asset_job",
        selection=adp_wfm_assets_daily,
    ),
    hour_of_day=23,
    minute_of_hour=50,
)

adp_wfm_dynamic_partition_asset_job = define_asset_job(
    name=f"{CODE_LOCATION}_adp_wfm_dynamic_partition_asset_job",
    selection=adp_wfm_assets_dynamic,
)


@schedule(
    name=f"{adp_wfm_dynamic_partition_asset_job.name}_schedule",
    cron_schedule="50 23 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
    job=define_asset_job(
        name=f"{CODE_LOCATION}_adp_wfm_dynamic_partition_asset_job",
        selection=adp_wfm_assets_dynamic,
    ),
)
def adp_wfm_dynamic_partition_schedule(
    context: ScheduleEvaluationContext, adp_wfm: AdpWorkforceManagerResource
) -> Generator:
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
                run_key=f"{context._schedule_name}_{partition_key}",
                partition_key=partition_key,
            )


schedules = [
    adp_wfm_daily_partition_asset_job_schedule,
    adp_wfm_dynamic_partition_schedule,
]
