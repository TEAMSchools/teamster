import json

from dagster import (
    AssetMaterialization,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.tableau.assets import external_assets
from teamster.libraries.tableau.resources import TableauServerResource


@sensor(
    name=f"{CODE_LOCATION}_tableau_asset_sensor",
    minimum_interval_seconds=(60 * 10),
    asset_selection=external_assets,
)
def tableau_asset_sensor(
    context: SensorEvaluationContext, tableau: TableauServerResource
):
    cursor: dict = json.loads(context.cursor or "{}")

    asset_events = []

    for asset in external_assets:
        asset_identifier = asset.key.to_python_identifier()
        asset_metadata = asset.metadata_by_key[asset.key]
        context.log.info(asset_identifier)

        last_updated_timestamp = cursor.get(asset_identifier, 0)

        workbook = tableau._server.workbooks.get_by_id(asset_metadata["id"])

        updated_at_timestamp = _check.not_none(value=workbook.updated_at).timestamp()

        if updated_at_timestamp > last_updated_timestamp:
            context.log.info(workbook.updated_at)

            asset_events.append(AssetMaterialization(asset_key=asset.key))

            cursor[asset_identifier] = updated_at_timestamp

    return SensorResult(asset_events=asset_events, cursor=json.dumps(cursor))


sensors = [
    tableau_asset_sensor,
]
