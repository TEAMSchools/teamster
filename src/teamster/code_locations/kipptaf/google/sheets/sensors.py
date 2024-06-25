import json

import pendulum
from dagster import (
    AssetMaterialization,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.google.sheets.assets import google_sheets_assets
from teamster.libraries.google.sheets.resources import GoogleSheetsResource

ASSET_KEYS_BY_SHEET_ID = {
    a.metadata_by_key[a.key]["sheet_id"]: [
        b.key
        for b in google_sheets_assets
        if b.metadata_by_key[b.key]["sheet_id"] == a.metadata_by_key[a.key]["sheet_id"]
    ]
    for a in google_sheets_assets
}.items()

TIMEOUT = 60 / len(ASSET_KEYS_BY_SHEET_ID)


@sensor(
    name=f"{CODE_LOCATION}_google_sheets_asset_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=google_sheets_assets,
)
def google_sheets_asset_sensor(
    context: SensorEvaluationContext, gsheets: GoogleSheetsResource
) -> SensorResult:
    cursor: dict = json.loads(context.cursor or "{}")
    asset_events: list = []

    gsheets._client.http_client.set_timeout(TIMEOUT)

    for sheet_id, asset_keys in ASSET_KEYS_BY_SHEET_ID:
        try:
            spreadsheet = _check.not_none(value=gsheets.open(sheet_id=sheet_id))

            last_update_time = _check.inst(
                pendulum.parse(text=spreadsheet.get_lastUpdateTime()), pendulum.DateTime
            )

            last_update_timestamp = last_update_time.timestamp()

            last_materialization_timestamp = cursor.get(sheet_id, 0)

            if last_update_timestamp > last_materialization_timestamp:
                context.log.info(asset_keys)
                asset_events.extend(
                    [
                        AssetMaterialization(asset_key=asset_key)
                        for asset_key in asset_keys
                    ]
                )

                cursor[sheet_id] = last_update_timestamp
        except Exception as e:
            context.log.error(e)

    return SensorResult(asset_events=asset_events, cursor=json.dumps(obj=cursor))


sensors = [
    google_sheets_asset_sensor,
]
