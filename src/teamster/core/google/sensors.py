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
from gspread.exceptions import APIError

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
            context.log.debug(asset.metadata["sheet_id"].value)

            try:
                spreadsheet = gsheets.open(sheet_id=asset.metadata["sheet_id"].value)

                last_update_timestamp = pendulum.parser.parse(
                    text=spreadsheet.lastUpdateTime
                ).timestamp()

                context.log.debug(f"last_update_time:\t{last_update_timestamp}")

                latest_observation_timestamp = cursor.get(asset_key_str, 0)

                context.log.debug(
                    f"last_observation_timestamp:\t{latest_observation_timestamp}"
                )

                if last_update_timestamp > latest_observation_timestamp:
                    asset_keys.append(asset_key_str)

                    cursor[asset_key_str] = last_update_timestamp
            except APIError as e:
                context.log.error(e)

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
