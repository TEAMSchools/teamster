import json
import time

import pendulum
from dagster import (
    AddDynamicPartitionsRequest,
    DynamicPartitionsDefinition,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)
from requests.exceptions import HTTPError

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.alchemer.assets import (
    survey,
    survey_metadata_assets,
    survey_response,
    survey_response_disqualified,
)
from teamster.libraries.alchemer.resources import AlchemerResource


@sensor(
    name=f"{CODE_LOCATION}_alchemer_survey_metadata_asset_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=survey_metadata_assets,
)
def alchemer_survey_metadata_asset_sensor(
    context: SensorEvaluationContext, alchemer: AlchemerResource
):
    now = pendulum.now(tz="America/New_York").start_of("minute")

    cursor: dict = json.loads(context.cursor or "{}")
    latest_materialization_event = context.instance.get_latest_materialization_event(
        survey.key
    )

    partitions_def = _check.inst(survey.partitions_def, DynamicPartitionsDefinition)

    run_requests = []
    dynamic_partitions_requests = []

    try:
        survey_list = alchemer._client.survey.list()
    except Exception as e:
        return SensorResult(skip_reason=str(e))

    for survey_obj in survey_list:
        context.log.info(msg=survey_obj["title"])

        survey_id = survey_obj["id"]
        modified_on = pendulum.from_format(
            string=survey_obj["modified_on"],
            fmt="YYYY-MM-DD HH:mm:ss",
            tz="America/New_York",
        )

        survey_cursor_timestamp = cursor.get(survey_id)

        is_run_request = False

        if latest_materialization_event is None or survey_cursor_timestamp is None:
            is_run_request = True
            context.log.info("INITIAL RUN")
        elif modified_on > pendulum.from_timestamp(
            timestamp=survey_cursor_timestamp, tz="America/New_York"
        ):
            is_run_request = True
            context.log.info(f"MODIFIED: {modified_on}")

        if is_run_request:
            dynamic_partitions_requests.append(
                AddDynamicPartitionsRequest(
                    partitions_def_name=_check.not_none(value=partitions_def.name),
                    partition_keys=[survey_id],
                )
            )

            run_requests.append(
                RunRequest(
                    run_key="_".join(
                        ["survey_metadata", survey_id, str(modified_on.timestamp())]
                    ),
                    asset_selection=[a.key for a in survey_metadata_assets],
                    partition_key=survey_id,
                )
            )

            cursor[survey_id] = now.timestamp()

    return SensorResult(
        run_requests=run_requests,
        cursor=json.dumps(obj=cursor),
        dynamic_partitions_requests=dynamic_partitions_requests,
    )


@sensor(
    name=f"{CODE_LOCATION}_alchemer_survey_response_asset_sensor",
    minimum_interval_seconds=(60 * 15),
    asset_selection=[survey_response, survey_response_disqualified],
)
def alchemer_survey_response_asset_sensor(
    context: SensorEvaluationContext, alchemer: AlchemerResource
):
    """https://apihelp.alchemer.com/help/api-response-time
    Response data is subject to response processing, which can vary based on server
    load. If you are looking to access response data, the time between when a
    response is submitted (even those submitted via the API) and when the data is
    available via the API can be upwards of 5 minutes.
    """
    now = pendulum.now(tz="America/New_York").subtract(minutes=15).start_of("minute")

    survey_response_partitions_def = _check.inst(
        survey_response.partitions_def, DynamicPartitionsDefinition
    )
    survey_response_disqualified_partitions_def = _check.inst(
        survey_response_disqualified.partitions_def, DynamicPartitionsDefinition
    )
    cursor: dict = json.loads(context.cursor or "{}")

    run_requests = []
    survey_response_partition_keys = []
    survey_response_dq_partition_keys = []

    try:
        surveys = alchemer._client.survey.list()
    except Exception as e:
        return SensorResult(skip_reason=str(e))

    for survey_metadata in surveys:
        survey_id = survey_metadata["id"]

        survey_cursor_timestamp = cursor.get(survey_id, 0)

        is_run_request = False
        run_config = None

        if survey_cursor_timestamp == 0:
            is_run_request = True
            run_config = {
                "execution": {
                    "config": {
                        "resources": {"limits": {"cpu": "500m", "memory": "4.0Gi"}}
                    }
                }
            }
        elif survey_metadata["status"] in ["Closed", "Archived"]:
            continue
        else:
            try:
                try:
                    survey_obj = alchemer._client.survey.get(id=survey_id)
                except Exception as e:
                    context.log.error(msg=e)
                    continue

                date_submitted = pendulum.from_timestamp(
                    timestamp=survey_cursor_timestamp, tz="America/New_York"
                )

                survey_response_data = survey_obj.response.filter(
                    "date_submitted", ">=", date_submitted.to_datetime_string()
                ).list(params={"resultsperpage": 1, "page": 1})

                if survey_response_data:
                    is_run_request = True
            except HTTPError as e:
                context.log.error(msg=e)

        if is_run_request:
            partition_key = f"{survey_id}_{survey_cursor_timestamp}"
            survey_response_partition_keys.append(partition_key)
            survey_response_dq_partition_keys.append(survey_id)

            run_requests.extend(
                [
                    RunRequest(
                        run_key=f"alchemer_survey_response_job_{partition_key}",
                        run_config=run_config,
                        asset_selection=[survey_response.key],
                        partition_key=partition_key,
                    ),
                    RunRequest(
                        run_key=f"alchemer_survey_response_dq_job_{partition_key}",
                        run_config=run_config,
                        asset_selection=[survey_response_disqualified.key],
                        partition_key=survey_id,
                    ),
                ]
            )

            cursor[survey_id] = now.timestamp()

        time.sleep(0.5)  # rate limit = 240 requests/min

    return SensorResult(
        run_requests=run_requests,
        cursor=json.dumps(obj=cursor),
        dynamic_partitions_requests=[
            AddDynamicPartitionsRequest(
                partitions_def_name=_check.not_none(
                    survey_response_partitions_def.name
                ),
                partition_keys=survey_response_partition_keys,
            ),
            AddDynamicPartitionsRequest(
                partitions_def_name=_check.not_none(
                    survey_response_disqualified_partitions_def.name
                ),
                partition_keys=survey_response_dq_partition_keys,
            ),
        ],
    )


sensors = [
    alchemer_survey_metadata_asset_sensor,
    alchemer_survey_response_asset_sensor,
]
