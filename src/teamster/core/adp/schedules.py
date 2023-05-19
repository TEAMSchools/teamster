from dagster import (
    AssetsDefinition,
    DynamicPartitionsDefinition,
    MultiPartitionKey,
    ResourceParam,
    RunRequest,
    ScheduleEvaluationContext,
    schedule,
)

from teamster.core.adp.resources import WorkforceManagerResource


def build_dynamic_partition_schedule(
    cron_schedule,
    code_location,
    source_system,
    execution_timezone,
    job,
    asset_defs: list[AssetsDefinition],
):
    @schedule(
        cron_schedule=cron_schedule,
        name=f"{code_location}_{source_system}_wfm_dynamic_partition_schedule",
        execution_timezone=execution_timezone.name,
        job=job,
    )
    def _schedule(
        context: ScheduleEvaluationContext,
        adp_wfm: ResourceParam[WorkforceManagerResource],
    ):
        for asset in asset_defs:
            date_partition: DynamicPartitionsDefinition = (
                asset.partitions_def.get_partitions_def_for_dimension("date")
            )
            symbolic_id_partition = (
                asset.partitions_def.get_partitions_def_for_dimension("symbolic_id")
            )

            for symbolic_id in symbolic_id_partition.get_partition_keys():
                symbolic_period_record = adp_wfm.request(
                    method="POST",
                    endpoint="v1/commons/symbolicperiod/read",
                    json={
                        "where": {
                            "currentUser": True,
                            "symbolicPeriodId": symbolic_id,
                        }
                    },
                ).json()

                partition_key = MultiPartitionKey(
                    {
                        "symbolic_id": symbolic_id,
                        "date": symbolic_period_record["begin"],
                    }
                )

                context.instance.add_dynamic_partitions(
                    partitions_def_name=date_partition.name,
                    partition_keys=[symbolic_period_record["begin"]],
                )

                yield RunRequest(
                    run_key=f"{asset.key.to_python_identifier()}_{partition_key}",
                    asset_selection=[asset.key],
                    partition_key=partition_key,
                )

    return _schedule
