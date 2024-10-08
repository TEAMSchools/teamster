import json

from dagster import (
    AssetMaterialization,
    AssetSpec,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_gcp import BigQueryResource
from google.cloud.bigquery import DatasetReference, TableReference

from teamster import GCS_PROJECT_NAME
from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._google.appsheet.assets import (
    asset_specs as google_appsheet_asset_specs,
)
from teamster.code_locations.kipptaf.airbyte.assets import (
    asset_specs as airbyte_asset_specs,
)

asset_selection: list[AssetSpec] = [*google_appsheet_asset_specs, *airbyte_asset_specs]


@sensor(
    name=f"{CODE_LOCATION}__google__bigquery__table_modified_sensor",
    minimum_interval_seconds=(60 * 5),
)
def bigquery_table_modified_sensor(
    context: SensorEvaluationContext, db_bigquery: BigQueryResource
):
    asset_events = []
    cursor: dict = json.loads(context.cursor or "{}")

    with db_bigquery.get_client() as bq:
        bq = bq

    for assets_def in asset_selection:
        python_identifier = assets_def.key.to_python_identifier()

        cursor_modified_timestamp = cursor.get(python_identifier, 0)

        table_ref = TableReference(
            dataset_ref=DatasetReference(
                project=GCS_PROJECT_NAME, dataset_id=assets_def.metadata["dataset_id"]
            ),
            table_id=assets_def.metadata["table_id"],
        )

        table = bq.get_table(table=table_ref)

        if table.modified is None:
            continue
        else:
            table_modified_timestamp = table.modified.timestamp()

        if table_modified_timestamp > cursor_modified_timestamp:
            context.log.info(msg=f"{assets_def.key}:\t{table_modified_timestamp}")
            asset_events.append(AssetMaterialization(asset_key=assets_def.key))
            cursor[python_identifier] = table_modified_timestamp

    if asset_events:
        return SensorResult(asset_events=asset_events, cursor=json.dumps(obj=cursor))


sensors = [
    bigquery_table_modified_sensor,
]
