import json

import pendulum
from dagster import RunConfig, RunRequest, SensorEvaluationContext, SensorResult, sensor
from gspread.exceptions import APIError

from ... import CODE_LOCATION
from ..resources import GoogleSheetsResource
from .assets import google_sheets_assets
from .jobs import asset_observation_job
from .ops import ObservationOpConfig

ASSET_KEYS_BY_SHEET_ID = {
    a.metadata["sheet_id"].value: [
        b.key
        for b in google_sheets_assets
        if b.metadata["sheet_id"].value == a.metadata["sheet_id"].value
    ]
    for a in google_sheets_assets
}


@sensor(
    name=f"{CODE_LOCATION}_google_sheets_asset_sensor",
    minimum_interval_seconds=(60 * 10),
    job=asset_observation_job,
)
def google_sheets_asset_sensor(
    context: SensorEvaluationContext, gsheets: GoogleSheetsResource
) -> SensorResult:
    cursor: dict = json.loads(context.cursor or "{}")

    requested_asset_keys = []
    for sheet_id, asset_keys in ASSET_KEYS_BY_SHEET_ID.items():
        context.log.info(sheet_id)

        try:
            spreadsheet = gsheets.open(sheet_id=sheet_id)

            last_update_timestamp = pendulum.parser.parse(
                text=spreadsheet.get_lastUpdateTime()
            ).timestamp()  # type: ignore

            last_materialization_timestamp = cursor.get(sheet_id, 0)

            if last_update_timestamp > last_materialization_timestamp:
                context.log.info(asset_keys)
                requested_asset_keys.extend(asset_keys)

                cursor[sheet_id] = last_update_timestamp
        except APIError as e:
            context.log.exception(e)

    return SensorResult(
        run_requests=[
            RunRequest(
                run_key=f"{context.sensor_name}_{pendulum.now().timestamp()}",
                run_config=RunConfig(
                    ops={
                        "asset_observation_op": ObservationOpConfig(
                            asset_keys=requested_asset_keys
                        )
                    }
                ),
            )
        ],
        cursor=json.dumps(obj=cursor),
    )


_all = [
    google_sheets_asset_sensor,
]
