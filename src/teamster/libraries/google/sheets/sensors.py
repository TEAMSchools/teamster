import json
from itertools import groupby

from dagster import (
    AssetKey,
    AssetMaterialization,
    AssetSpec,
    SensorDefinition,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)

from teamster.libraries.google.drive.resources import GoogleDriveResource


def build_google_sheets_asset_sensor(
    code_location: str,
    minimum_interval_seconds: int,
    asset_specs: list[AssetSpec],
) -> SensorDefinition:
    @sensor(
        name=f"{code_location}__google__sheets__asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext, google_drive: GoogleDriveResource
    ) -> SensorResult | SkipReason:
        def get_sheet_id(asset_spec: AssetSpec) -> str:
            return asset_spec.metadata["sheet_id"]

        cursor: dict[str, float] = json.loads(context.cursor or "{}")
        asset_events: list[AssetMaterialization] = []

        sheet_id_to_asset_keys: dict[str, list[AssetKey]] = {
            sheet_id: [g.key for g in group]
            for sheet_id, group in groupby(
                iterable=sorted(asset_specs, key=get_sheet_id), key=get_sheet_id
            )
        }

        modified_times = google_drive.get_modified_times(
            file_ids=list(sheet_id_to_asset_keys.keys())
        )

        for sheet_id, asset_keys in sheet_id_to_asset_keys.items():
            if sheet_id not in modified_times:
                continue  # 5xx was logged by the resource; skip

            last_update_timestamp = modified_times[sheet_id]
            last_materialization_timestamp = cursor.get(sheet_id, 0)

            if last_update_timestamp > last_materialization_timestamp:
                context.log.info(asset_keys)
                asset_events.extend(
                    AssetMaterialization(asset_key=asset_key)
                    for asset_key in asset_keys
                )

                cursor[sheet_id] = last_update_timestamp

        if asset_events:
            return SensorResult(
                asset_events=asset_events, cursor=json.dumps(obj=cursor)
            )
        else:
            return SkipReason()

    return _sensor
