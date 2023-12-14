import json

import pendulum
from dagster import AssetMaterialization, SensorEvaluationContext, SensorResult, sensor
from gspread.exceptions import APIError

from ... import CODE_LOCATION
from ..resources import GoogleSheetsResource


def build_google_sheets_asset_sensor(asset_defs):
    asset_keys_by_sheet_id = {
        a.metadata_by_key[a.key]["sheet_id"]: [
            b.key
            for b in asset_defs
            if b.metadata_by_key[b.key]["sheet_id"]
            == a.metadata_by_key[a.key]["sheet_id"]
        ]
        for a in asset_defs
    }

    @sensor(
        name=f"{CODE_LOCATION}_google_sheets_asset_sensor",
        minimum_interval_seconds=(60 * 10),
    )
    def _sensor(
        context: SensorEvaluationContext, gsheets: GoogleSheetsResource
    ) -> SensorResult:
        cursor: dict = json.loads(context.cursor or "{}")

        asset_events = []
        for sheet_id, asset_keys in asset_keys_by_sheet_id.items():
            context.log.info(sheet_id)

            try:
                spreadsheet = gsheets.open(sheet_id=sheet_id)

                last_update_timestamp = pendulum.parser.parse(
                    text=spreadsheet.get_lastUpdateTime()
                ).timestamp()  # type: ignore

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
            except APIError as e:
                context.log.exception(e)

        return SensorResult(asset_events=asset_events, cursor=json.dumps(obj=cursor))

    return _sensor
