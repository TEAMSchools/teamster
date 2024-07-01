import json

from dagster import (
    AssetMaterialization,
    AssetsDefinition,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)

from teamster.libraries.tableau.resources import TableauServerResource


def build_tableau_asset_sensor(
    name: str, asset_selection: list[AssetsDefinition], minimum_interval_seconds
):
    @sensor(
        name=name,
        asset_selection=asset_selection,
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, tableau: TableauServerResource):
        cursor: dict = json.loads(context.cursor or "{}")

        asset_events = []

        for asset in asset_selection:
            asset_identifier = asset.key.to_python_identifier()
            asset_metadata = asset.metadata_by_key[asset.key]
            context.log.info(asset_identifier)

            last_updated_timestamp = cursor.get(asset_identifier, 0)

            workbook = tableau._server.workbooks.get_by_id(asset_metadata["id"])

            updated_at_timestamp = _check.not_none(
                value=workbook.updated_at
            ).timestamp()

            if updated_at_timestamp > last_updated_timestamp:
                context.log.info(workbook.updated_at)

                asset_events.append(AssetMaterialization(asset_key=asset.key))

                cursor[asset_identifier] = updated_at_timestamp

        return SensorResult(asset_events=asset_events, cursor=json.dumps(cursor))

    return _sensor
