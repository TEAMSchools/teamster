from dagster import (  # RunRequest,
    AssetsDefinition,
    DynamicPartitionsDefinition,
    ScheduleEvaluationContext,
    schedule,
)

from teamster.core.sqlalchemy.resources import OracleResource


def build_dynamic_partition_schedule(
    cron_schedule,
    code_location,
    source_system,
    execution_timezone,
    asset_defs: list[AssetsDefinition],
):
    @schedule(
        cron_schedule=cron_schedule,
        name=f"{code_location}_{source_system}_dynamic_partition_schedule",
        execution_timezone=execution_timezone,
    )
    def _schedule(context: ScheduleEvaluationContext, db_powerschool: OracleResource):
        for asset in asset_defs:
            partitions_def: DynamicPartitionsDefinition = asset.partitions_def

            partitions = sorted(
                context.instance.get_dynamic_partitions(partitions_def.name)
            )

            context.log.info(asset.key.to_user_string())
            context.log.info(partitions)
            context.log.info(partitions[-1])

            # context.instance.add_dynamic_partitions(
            #     partitions_def_name=partitions_def.name,
            #     partition_keys=[...],
            # )

        # yield RunRequest(
        #     run_key=f"{code_location}_powerschool_dynamic_schedule_{...}",
        #     asset_selection=[...],
        #     partition_key=partition_key,
        # )

    return _schedule
