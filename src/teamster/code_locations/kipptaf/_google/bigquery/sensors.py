import json

from dagster import AssetMaterialization, SensorEvaluationContext, SensorResult, sensor
from dagster_gcp import BigQueryResource
from google.cloud.bigquery import DatasetReference, TableReference

from teamster import GCS_PROJECT_NAME
from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf._google.appsheet.assets import (
    assets as google_appsheet_assets,
)
from teamster.code_locations.kipptaf.airbyte.assets import assets as airbyte_assets
from teamster.code_locations.kipptaf.fivetran.assets import assets as fivetran_assets

asset_selection = [*google_appsheet_assets, *airbyte_assets, *fivetran_assets]


@sensor(
    name=f"{CODE_LOCATION}_bigquery_table_modified_sensor",
    minimum_interval_seconds=(60 * 5),
)
def bigquery_table_modified_sensor(
    context: SensorEvaluationContext, db_bigquery: BigQueryResource
):
    asset_events = []
    cursor = json.loads(context.cursor or "{}")

    with db_bigquery.get_client() as bq:
        bq = bq

    for assets_def in asset_selection:
        python_identifier = assets_def.key.to_python_identifier()
        metadata = assets_def.metadata_by_key[assets_def.key]

        cursor_modified_timestamp = cursor.get(python_identifier, 0)

        table_ref = TableReference(
            dataset_ref=DatasetReference(
                project=GCS_PROJECT_NAME, dataset_id=metadata["dataset_id"]
            ),
            table_id=metadata["table_id"],
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
