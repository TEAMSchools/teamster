from dagster import (
    AssetObservation,
    AssetsDefinition,
    MultiPartitionKey,
    MultiPartitionsDefinition,
    RunRequest,
    ScheduleEvaluationContext,
    SkipReason,
    _check,
    define_asset_job,
    job,
    schedule,
)

from teamster.libraries.tableau.resources import TableauServerResource


def build_tableau_workbook_stats_schedule(
    asset_def: AssetsDefinition, cron_schedule, execution_timezone
):
    job = define_asset_job(
        name=f"{asset_def.key.to_python_identifier()}_asset_job", selection=[asset_def]
    )

    @schedule(
        name=f"{job.name}_schedule",
        job=job,
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
    )
    def _schedule(context: ScheduleEvaluationContext):
        partitions_def = _check.inst(
            asset_def.partitions_def, MultiPartitionsDefinition
        )

        workbook_id_partition = partitions_def.get_partitions_def_for_dimension(
            "workbook_id"
        )
        date_partition = partitions_def.get_partitions_def_for_dimension("date")

        workbook_id_partition_keys = workbook_id_partition.get_partition_keys()
        last_date_partition_key = _check.not_none(
            value=date_partition.get_last_partition_key()
        )

        for workbook_id in workbook_id_partition_keys:
            partition_key = MultiPartitionKey(
                {"workbook_id_partition": workbook_id, "date": last_date_partition_key}
            )

            yield RunRequest(
                run_key=f"{context._schedule_name}_{partition_key}",
                asset_selection=[asset_def.key],
                partition_key=partition_key,
                tags={"tableau_pat_session_limit": "true"},
            )

    return _schedule


def build_tableau_workbook_refresh_schedule(
    asset: AssetsDefinition, execution_timezone: str
):
    @job(name=f"{asset.key.to_python_identifier()}_job")
    def _job():
        """Placehoder job"""

    @schedule(
        name=f"{_job.name}_schedule",
        cron_schedule=asset.metadata_by_key[asset.key]["cron_schedule"],
        execution_timezone=execution_timezone,
        job=_job,
    )
    def _schedule(context: ScheduleEvaluationContext, tableau: TableauServerResource):
        workbook = tableau._server.workbooks.get_by_id(
            asset.metadata_by_key[asset.key]["id"]
        )

        job = tableau._server.workbooks.refresh(workbook)

        context.log.info(msg=str(job))

        context.instance.report_runless_asset_event(
            AssetObservation(asset_key=asset.key)
        )

        return SkipReason("This schedule doesn't actually return any runs.")

    return _schedule
