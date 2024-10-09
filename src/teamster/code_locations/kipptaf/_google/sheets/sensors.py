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

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._google.sheets.assets import asset_specs
from teamster.libraries.google.sheets.resources import GoogleSheetsResource


@sensor(
    name=f"{CODE_LOCATION}_google_sheets_asset_sensor",
    minimum_interval_seconds=(60 * 10),
)
def google_sheets_asset_sensor(
    context: SensorEvaluationContext, gsheets: GoogleSheetsResource
):
    cursor: dict = json.loads(context.cursor or "{}")
    asset_events: list = []

    for sheet_id, group in groupby(
        iterable=asset_specs, key=lambda x: x.metadata["sheet_id"]
    ):
        asset_keys = [g.key for g in group]

        spreadsheet = _check.not_none(value=gsheets.open(sheet_id=sheet_id))

        last_update_timestamp = datetime.fromisoformat(
            spreadsheet.get_lastUpdateTime()
        ).timestamp()

        last_materialization_timestamp = cursor.get(sheet_id, 0)

        context.log.debug(
            msg=(
                f"{sheet_id}: "
                f"{last_update_timestamp} > {last_materialization_timestamp}: "
                f"{last_update_timestamp > last_materialization_timestamp}"
            )
        )

        if last_update_timestamp > last_materialization_timestamp:
            context.log.info(asset_keys)
            asset_events.extend(
                [AssetMaterialization(asset_key=asset_key) for asset_key in asset_keys]
            )

            cursor[sheet_id] = last_update_timestamp

    if asset_events:
        return SensorResult(asset_events=asset_events, cursor=json.dumps(obj=cursor))


sensors = [
    google_sheets_asset_sensor,
]
