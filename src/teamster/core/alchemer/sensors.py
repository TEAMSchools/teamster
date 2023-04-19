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
        cursor: dict = json.loads(context.cursor or "{}")

        now = pendulum.now(tz=LOCAL_TIME_ZONE).start_of("minute")

        surveys = alchemer.survey.list()
        for survey in surveys:
            survey_id = survey["id"]
            modified_on = pendulum.from_format(
                string=survey["modified_on"],
                fmt="YYYY-MM-DD HH:mm:ss",
                tz="US/Eastern",
            )

            survey_cursor_timestamp = cursor.get(survey_id)

            if (
                not context.instance.get_latest_materialization_event(survey_asset.key)
                or survey_cursor_timestamp is None
            ):
                run_request = True
            elif modified_on > pendulum.from_timestamp(
                timestamp=survey_cursor_timestamp, tz=LOCAL_TIME_ZONE
            ):
                run_request = True
            else:
                run_request = False

            if run_request:
                context.instance.add_dynamic_partitions(
                    partitions_def_name=survey_asset.partitions_def.name,
                    partition_keys=[survey_id],
                )

                yield RunRequest(
                    run_key=f"{asset_job.name}_{survey_id}",
                    asset_selection=asset_keys,
                    partition_key=survey_id,
                )

                cursor[survey_id] = now.timestamp()

        context.update_cursor(json.dumps(cursor))

    return _sensor
