from datetime import datetime, timezone

from dagster import (
    AssetsDefinition,
    DagsterEventType,
    DynamicPartitionsDefinition,
    EventRecordsFilter,
    RunRequest,
    ScheduleEvaluationContext,
    schedule,
)
from dagster_shared import check

from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)


def build_pse_submission_records_schedule(
    target: AssetsDefinition, cron_schedule: str, execution_timezone: str
):
    @schedule(
        name=f"{target.key.to_python_identifier()}_schedule",
        cron_schedule=cron_schedule,
        execution_timezone=execution_timezone,
        target=target,
    )
    def _schedule(
        context: ScheduleEvaluationContext, ps_enrollment: PowerSchoolEnrollmentResource
    ):
        now_timestamp = datetime.now(timezone.utc).timestamp()

        run_requests: list[RunRequest] = []

        partitions_def = check.inst(
            obj=target.partitions_def, ttype=DynamicPartitionsDefinition
        )

        published_actions = ps_enrollment.get(endpoint="publishedactions")

        partition_keys = [str(pa["id"]) for pa in published_actions]

        context.instance.add_dynamic_partitions(
            partitions_def_name=check.not_none(value=partitions_def.name),
            partition_keys=partition_keys,
        )

        for pa_id in partitions_def.get_partition_keys(
            dynamic_partitions_store=context.instance
        ):
            latest_materialization_event = context.instance.get_event_records(
                EventRecordsFilter(
                    asset_key=target.key,
                    event_type=DagsterEventType.ASSET_MATERIALIZATION,
                    asset_partitions=[pa_id],
                ),
                limit=1,
            )

            if latest_materialization_event:
                materialization_metadata = check.not_none(
                    value=latest_materialization_event[0].asset_materialization
                ).metadata

                materialization_records = materialization_metadata["records"].value
            else:
                materialization_records = 0

            metadata, _ = ps_enrollment.get(
                endpoint=f"publishedactions/{pa_id}/submissionrecords"
            ).values()

            if materialization_records != metadata["recordCount"]:
                context.log.info(msg=pa_id)
                run_requests.append(
                    RunRequest(
                        run_key=f"{context._schedule_name}__{pa_id}__{now_timestamp}",
                        partition_key=pa_id,
                    )
                )

        return run_requests

    return _schedule
