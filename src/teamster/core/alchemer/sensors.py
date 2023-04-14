import json

import pendulum
from alchemer import AlchemerSession
from dagster import AssetKey, ResourceParam, RunRequest, SensorEvaluationContext, sensor

from teamster.core.utils.variables import LOCAL_TIME_ZONE


def build_survey_metadata_asset_sensor(code_location, minimum_interval_seconds=None):
    @sensor(
        name="alchemer_survey_metadata_asset_sensor",
        job=asset_job,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext, alchemer: ResourceParam[AlchemerSession]
    ):
        survey_asset = [
            asset
            for asset in asset_defs
            if asset.key == AssetKey([code_location, "alchemer", "survey"])
        ]

        cursor = json.loads(context.cursor or "{}")

        window_end = (
            pendulum.now(tz=LOCAL_TIME_ZONE).subtract(minutes=30).start_of("minute")
        )

        surveys = alchemer.survey.list()

        for survey in surveys:
            context.log.debug(survey["title"])
            survey_id = survey["id"]

            # check if static paritition has ever been materialized
            asset_materialization_counts = (
                context.instance.get_materialization_count_by_partition(
                    [survey_asset.key]
                ).get(survey_asset.key, {})
            )

            static_materialization_count = 0
            for partition_key, count in asset_materialization_counts.items():
                if partition_key == survey_id:
                    static_materialization_count += count

            run_request = False

            if (
                static_materialization_count == 0
                or static_materialization_count == context.retry_number
            ):
                window_start = pendulum.from_timestamp(0)
                run_request = True
                run_config = {
                    "execution": {
                        "config": {
                            "resources": {"limits": {"cpu": "750m", "memory": "1.0Gi"}}
                        }
                    }
                }
            else:
                # check modified_on/status for survey id
                window_start = pendulum.from_timestamp(
                    cursor.get(survey_id), tz=LOCAL_TIME_ZONE
                )

                if survey["modified_on"] > window_start:
                    ...
                    run_request = True
                    run_config = None

        if run_request:
            partition_key = window_start.timestamp()

            context.instance.add_dynamic_partitions(
                partitions_def_name=survey_asset.partitions_def.name,
                partition_keys=[partition_key],
            )

            yield RunRequest(
                run_key=f"{asset_job.name}_{window_start.int_timestamp}",
                run_config=run_config,
                job_name="",
                asset_selection=[survey_asset.key],
                partition_key=partition_key,
            )

            cursor[survey_id] = window_end.timestamp()

        context.update_cursor(json.dumps(cursor))

    return _sensor
