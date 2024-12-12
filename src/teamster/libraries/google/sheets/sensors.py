import json
from datetime import datetime
from itertools import groupby

from dagster import (
    AssetMaterialization,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)
from gspread.exceptions import APIError

from teamster.libraries.google.sheets.resources import GoogleSheetsResource


def build_google_sheets_asset_sensor(
    code_location: str, minimum_interval_seconds: int, asset_specs: list
):
    @sensor(
        name=f"{code_location}_google_sheets_asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, gsheets: GoogleSheetsResource):
        cursor: dict = json.loads(context.cursor or "{}")
        asset_events: list = []

        # TODO: add asset event for newly created specs
        for sheet_id, group in groupby(
            iterable=asset_specs, key=lambda x: x.metadata["sheet_id"]
        ):
            asset_keys = [g.key for g in group]

            try:
                spreadsheet = _check.not_none(value=gsheets.open(sheet_id=sheet_id))
            except APIError as e:
                if str(e.code)[0] == "5":
                    context.log.error(msg=str(e))
                    continue
                else:
                    raise e

            last_update_timestamp = datetime.fromisoformat(
                spreadsheet.get_lastUpdateTime()
            ).timestamp()

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

        if asset_events:
            return SensorResult(
                asset_events=asset_events, cursor=json.dumps(obj=cursor)
            )

    return _sensor
