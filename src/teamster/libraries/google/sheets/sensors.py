import json
from itertools import groupby

from dagster import (
    AssetMaterialization,
    AssetSpec,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from googleapiclient.errors import HttpError

from teamster.libraries.google.drive.resources import GoogleDriveResource


def build_google_sheets_asset_sensor(
    code_location: str, minimum_interval_seconds: int, asset_specs: list
):
    @sensor(
        name=f"{code_location}__google__sheets__asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, google_drive: GoogleDriveResource):
        def get_sheet_id(asset_spec: AssetSpec) -> str:
            return asset_spec.metadata["sheet_id"]

        cursor: dict[str, float] = json.loads(context.cursor or "{}")
        asset_events: list[AssetMaterialization] = []

        for sheet_id, group in groupby(
            iterable=sorted(asset_specs, key=get_sheet_id), key=get_sheet_id
        ):
            asset_keys = [g.key for g in group]

            try:
                last_update_timestamp = google_drive.get_modified_time(file_id=sheet_id)
            except HttpError as e:
                if e.resp.status >= 500:
                    context.log.error(msg=str(e))
                    continue
                else:
                    raise

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
        else:
            return SkipReason()

    return _sensor
