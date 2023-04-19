import json

import pendulum
from alchemer import AlchemerSession
from dagster import (
    AssetKey,
    AssetsDefinition,
    ResourceParam,
    RunRequest,
    SensorEvaluationContext,
    define_asset_job,
    sensor,
)

from teamster.core.utils.variables import LOCAL_TIME_ZONE


def build_survey_metadata_asset_sensor(
    code_location, asset_defs: list[AssetsDefinition], minimum_interval_seconds=None
):
    asset_keys = [a.key for a in asset_defs]

    survey_asset = [
        asset
        for asset in asset_defs
        if asset.key == AssetKey([code_location, "alchemer", "survey"])
    ][0]

    asset_job = define_asset_job(
        name="survey_metadata_job",
        selection=asset_keys,
        partitions_def=survey_asset.partitions_def,
    )

    @sensor(
        name="alchemer_survey_metadata_asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        job=asset_job,
    )
    def _sensor(
        context: SensorEvaluationContext, alchemer: ResourceParam[AlchemerSession]
    ):
        now = pendulum.now(tz=LOCAL_TIME_ZONE).start_of("minute")

        cursor = json.loads(context.cursor or "{}")

        surveys = alchemer.survey.list()
        for survey in surveys:
            survey_id = survey["id"]
            modified_on = pendulum.from_format(
                string=survey["modified_on"],
                fmt="YYYY-MM-DD HH:mm:ss",
                tz="US/Eastern",
            )

            context.log.debug(survey["title"])

            # check if survey id has ever been materialized
            materialization_count_by_partition = (
                context.instance.get_materialization_count_by_partition(
                    [survey_asset.key]
                ).get(survey_asset.key, {})
            )

            materialization_count = 0
            for partition_key, count in materialization_count_by_partition.items():
                if partition_key == survey_id:
                    materialization_count += count

            run_request = False
            if (
                materialization_count == 0
                or materialization_count == context.retry_number
            ):
                run_request = True
                last_requested = pendulum.from_timestamp(0)
            else:
                # check modified_on for survey id
                last_requested = pendulum.from_timestamp(
                    timestamp=cursor.get(survey_id), tz=LOCAL_TIME_ZONE
                )

                if modified_on > last_requested:
                    run_request = True

        if run_request:
            partition_key = survey_id

            context.instance.add_dynamic_partitions(
                partitions_def_name=survey_asset.partitions_def.name,
                partition_keys=[partition_key],
            )

            yield RunRequest(
                run_key=f"{asset_job.name}_{partition_key}",
                asset_selection=asset_keys,
                partition_key=partition_key,
            )

            cursor[survey_id] = now.timestamp()

        context.update_cursor(json.dumps(cursor))

    return _sensor
