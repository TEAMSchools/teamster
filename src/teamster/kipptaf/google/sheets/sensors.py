import json

import pendulum
from dagster import RunConfig, RunRequest, SensorEvaluationContext, SensorResult, sensor
from gspread.exceptions import APIError

from teamster.core.utils.jobs import asset_observation_job
from teamster.core.utils.ops import ObservationOpConfig

from ... import CODE_LOCATION
from .assets import google_sheets_assets
from .resources import GoogleSheetsResource


@sensor(
    name=f"{CODE_LOCATION}_google_sheets_asset_sensor",
    minimum_interval_seconds=(60 * 10),
    job=asset_observation_job,
)
def google_sheets_asset_sensor(
    context: SensorEvaluationContext, gsheets: GoogleSheetsResource
):
    cursor: dict = json.loads(context.cursor or "{}")

    asset_keys = []
    for asset in google_sheets_assets:
        asset_key_str = asset.key.to_user_string()

        context.log.info(f"{asset_key_str}:\t" + asset.metadata["sheet_id"].value)

        try:
            spreadsheet = gsheets.open(sheet_id=asset.metadata["sheet_id"].value)

            last_update_timestamp = pendulum.parser.parse(
                text=spreadsheet.lastUpdateTime
            ).timestamp()

            latest_observation_timestamp = cursor.get(asset_key_str, 0)

            if last_update_timestamp > latest_observation_timestamp:
                context.log.debug(f"last_update_time:\t{last_update_timestamp}")
                context.log.debug(
                    f"last_observation_timestamp:\t{latest_observation_timestamp}"
                )

                asset_keys.append(asset_key_str)

                cursor[asset_key_str] = last_update_timestamp
        except APIError as e:
            context.log.exception(e)

    if asset_keys:
        run_config = RunConfig(
            ops={"asset_observation_op": ObservationOpConfig(asset_keys=asset_keys)}
        )

        return SensorResult(
            run_requests=[
                RunRequest(
                    run_key=f"{context._sensor_name}_{pendulum.now().timestamp()}",
                    run_config=run_config,
                )
            ],
            cursor=json.dumps(obj=cursor),
        )
