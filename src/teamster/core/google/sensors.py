import json

import pendulum
from dagster import (
    RunConfig,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SourceAsset,
    sensor,
)

from teamster.core.google.resources.sheets import GoogleSheetsResource
from teamster.core.utils.jobs import asset_observation_job
from teamster.core.utils.ops import ObservationOpConfig


def build_gsheet_sensor(
    code_location,
    asset_defs: list[SourceAsset],
    minimum_interval_seconds=None,
):
    @sensor(
        name=f"{code_location}_gsheets_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        job=asset_observation_job,
    )
    def _sensor(context: SensorEvaluationContext, gsheets: GoogleSheetsResource):
        cursor: dict = json.loads(context.cursor or "{}")

        asset_keys = []
        for asset in asset_defs:
            asset_key_str = asset.key.to_user_string()

            context.log.info(asset_key_str)

            spreadsheet = gsheets.open(sheet_id=asset.metadata["sheet_id"].value)

            last_update_timestamp = pendulum.parser.parse(
                text=spreadsheet.lastUpdateTime
            ).timestamp()

            context.log.debug(f"last_update_time:\t{last_update_timestamp}")

            latest_materialization_event = (
                context.instance.get_latest_materialization_event(asset.key)
            )

            latest_materialization_timestamp = (
                latest_materialization_event.timestamp
                if latest_materialization_event
                else 0
            )

            context.log.debug(
                "latest_materialization_event:\t"
                + str(latest_materialization_timestamp)
            )

            if last_update_timestamp > latest_materialization_timestamp:
                asset_keys.append(asset_key_str)

                cursor[asset_key_str] = last_update_timestamp

        if asset_keys:
            return SensorResult(
                run_requests=[
                    RunRequest(
                        run_key=f"{context._sensor_name}_{pendulum.now().timestamp()}",
                        run_config=RunConfig(
                            ops={
                                "asset_observation_op": ObservationOpConfig(
                                    asset_keys=asset_keys
                                )
                            }
                        ),
                    )
                ],
                cursor=json.dumps(obj=cursor),
            )

    return _sensor
