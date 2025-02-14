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
from dagster_fivetran import FivetranWorkspace
from dagster_fivetran.translator import FivetranConnector
from dagster_gcp import BigQueryResource
from google.cloud.bigquery import DatasetReference, TableReference


def build_fivetran_connector_sync_status_sensor(
    code_location: str,
    minimum_interval_seconds: int,
    asset_selection: list[AssetSpec],
    project: str,
):
    @sensor(
        name=f"{code_location}__fivetran__connector_sync_status_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(
        context: SensorEvaluationContext,
        fivetran: FivetranWorkspace,
        db_bigquery: BigQueryResource,
    ):
        asset_events = []
        connector_updated_assets: list[AssetSpec] = []

        cursor: dict[str, dict] = json.loads(
            s=context.cursor or json.dumps(obj={"connectors": {}, "assets": {}})
        )

        fivetran_client = fivetran.get_client()

        for connector_id, connector_assets in groupby(
            iterable=asset_selection, key=lambda a: a.metadata["connector_id"]
        ):
            previous_sync_completed_at = cursor["connectors"].get(connector_id, 0)

            connector = FivetranConnector.from_connector_details(
                connector_details=fivetran_client.get_connector_details(connector_id)
            )

            context.log.info(
                msg=(
                    f"{connector.name}: "
                    f"{'Succeeded' if connector.is_last_sync_successful else 'Failed'} "
                    f"{connector.last_sync_completed_at}"
                )
            )

            last_sync_completed_at_ts = connector.last_sync_completed_at.timestamp()

            if (
                connector.is_last_sync_successful
                and last_sync_completed_at_ts > previous_sync_completed_at
            ):
                connector_updated_assets.extend(connector_assets)
                cursor["connectors"][connector_id] = last_sync_completed_at_ts

        if connector_updated_assets:
            with db_bigquery.get_client() as bq:
                bq = bq
        else:
            return SkipReason("No connector syncs completed since last tick")

        for assets_def in connector_updated_assets:
            python_identifier = assets_def.key.to_python_identifier()

            cursor_table_modified_timestamp = cursor["assets"].get(python_identifier, 0)

            table_ref = TableReference(
                dataset_ref=DatasetReference(
                    project=project, dataset_id=assets_def.metadata["dataset_id"]
                ),
                table_id=assets_def.metadata["table_id"],
            )

            table = bq.get_table(table=table_ref)

            if table.modified is None:
                continue
            else:
                table_modified_timestamp = table.modified.timestamp()

            if table_modified_timestamp > cursor_table_modified_timestamp:
                context.log.info(msg=f"{assets_def.key}:\t{table_modified_timestamp}")
                asset_events.append(AssetMaterialization(asset_key=assets_def.key))
                cursor["assets"][python_identifier] = table_modified_timestamp

        if asset_events:
            return SensorResult(
                asset_events=asset_events, cursor=json.dumps(obj=cursor)
            )

    return _sensor
