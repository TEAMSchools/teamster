import json

import pendulum
from dagster import (
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SourceAsset,
    sensor,
)

from teamster.core.google.resources.sheets import GoogleSheetsResource


def build_gsheet_sensor(
    code_location,
    asset_defs: list[SourceAsset],
    minimum_interval_seconds=None,
):
    @sensor(
        name=f"{code_location}_gsheets_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        # asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(context: SensorEvaluationContext, gsheets: GoogleSheetsResource):
        cursor: dict = json.loads(context.cursor or "{}")

        for asset in asset_defs:
            asset_key_str = asset.key.to_python_identifier()

            context.log.info(asset_key_str)

            spreadsheet = gsheets.open(
                sheet_id=asset.metadata_by_key[asset.key]["sheet_id"]
            )

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
                yield RunRequest(
                    run_key=f"{asset_key_str}_{last_update_timestamp}",
                    asset_selection=[asset.key],
                )

                cursor[asset_key_str] = last_update_timestamp

    return _sensor
