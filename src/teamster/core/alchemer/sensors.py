import json

import pendulum
from alchemer import AlchemerSession
from dagster import (
    AddDynamicPartitionsRequest,
    AssetKey,
    AssetsDefinition,
    AssetSelection,
    DeleteDynamicPartitionsRequest,
    ResourceParam,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    define_asset_job,
    sensor,
)
from requests.exceptions import HTTPError


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
        name=f"{code_location}_alchemer_survey_metadata_job",
        selection=asset_keys,
        partitions_def=survey_asset.partitions_def,
    )

    @sensor(
        name=f"{code_location}_alchemer_survey_metadata_asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        job=asset_job,
    )
    def _sensor(
        context: SensorEvaluationContext, alchemer: ResourceParam[AlchemerSession]
    ):
        cursor: dict = json.loads(context.cursor or "{}")

        now = pendulum.now(tz="US/Eastern").start_of("minute")

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
                is_run_request = True
            elif modified_on > pendulum.from_timestamp(
                timestamp=survey_cursor_timestamp, tz="US/Eastern"
            ):
                is_run_request = True
            else:
                is_run_request = False

            if is_run_request:
                context.instance.add_dynamic_partitions(
                    partitions_def_name=survey_asset.partitions_def.name,
                    partition_keys=[survey_id],
                )

                yield RunRequest(
                    run_key=f"{code_location}_{asset_job.name}_{survey_id}",
                    asset_selection=asset_keys,
                    partition_key=survey_id,
                )

                cursor[survey_id] = now.timestamp()

        context.update_cursor(json.dumps(cursor))

    return _sensor


def build_survey_response_asset_sensor(
    code_location, asset_def: AssetsDefinition, minimum_interval_seconds=None
):
    @sensor(
        name=f"{code_location}_alchemer_survey_response_asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(asset_def),
    )
    def _sensor(
        context: SensorEvaluationContext, alchemer: ResourceParam[AlchemerSession]
    ):
        dynamic_partitions = context.instance.get_dynamic_partitions(
            asset_def.partitions_def.name
        )
        get_materialization_count_by_partition = (
            context.instance.get_materialization_count_by_partition(
                asset_keys=[asset_def.key]
            )
        )

        delete_partitions = [
            p
            for p in dynamic_partitions
            if p not in get_materialization_count_by_partition.get(asset_def.key)
            and p
            not in [
                "6580731_1682090760.0",
                "4561325_1682094300.0",
                "6829997_1682087700.0",
            ]
        ]

        cursor: dict = json.loads(context.cursor or "{}")

        """ https://apihelp.alchemer.com/help/api-response-time
        Response data is subject to response processing, which can vary based on server
        load. If you are looking to access response data, the time between when a
        response is submitted (even those submitted via the API) and when the data is
        available via the API can be upwards of 5 minutes.
        """
        now = pendulum.now(tz="US/Eastern").subtract(minutes=15).start_of("minute")

        try:
            surveys = alchemer.survey.list()
        except HTTPError as e:
            context.log.error(e)
            return

        run_requests = []
        add_partitions = []
        for survey_metadata in surveys:
            survey_id = survey_metadata["id"]

            survey_cursor_timestamp = cursor.get(survey_id, 0)

            if survey_cursor_timestamp == 0:
                is_run_request = True
                run_config = {
                    "execution": {
                        "config": {
                            "resources": {"limits": {"cpu": "1000m", "memory": "6.5Gi"}}
                        }
                    }
                }
            else:
                try:
                    survey = alchemer.survey.get(id=survey_id)

                    date_submitted = pendulum.from_timestamp(
                        timestamp=survey_cursor_timestamp, tz="US/Eastern"
                    )

                    survey_response_data = survey.response.filter(
                        "date_submitted", ">=", date_submitted.to_datetime_string()
                    ).list(params={"resultsperpage": 1, "page": 1})

                    if survey_response_data:
                        is_run_request = True
                    else:
                        is_run_request = False
                except HTTPError as e:
                    context.log.error(e)
                    is_run_request = False
                finally:
                    run_config = None

            if is_run_request:
                partition_key = f"{survey_id}_{survey_cursor_timestamp}"
                add_partitions.append(partition_key)

                # context.instance.add_dynamic_partitions(
                #     partitions_def_name=asset_def.partitions_def.name,
                #     partition_keys=[partition_key],
                # )

                run_requests.append(
                    RunRequest(
                        run_key=(
                            f"{code_location}_alchemer_survey_response_job_{partition_key}"
                        ),
                        run_config=run_config,
                        asset_selection=[asset_def.key],
                        partition_key=partition_key,
                    )
                )

                cursor[survey_id] = now.timestamp()

        # context.update_cursor(json.dumps(cursor))
        return SensorResult(
            run_requests=run_requests,
            dynamic_partitions_requests=[
                AddDynamicPartitionsRequest(
                    partitions_def_name=asset_def.partitions_def.name,
                    partition_keys=add_partitions,
                ),
                DeleteDynamicPartitionsRequest(
                    partitions_def_name=asset_def.partitions_def.name,
                    partition_keys=delete_partitions,
                ),
            ],
        )

    return _sensor
