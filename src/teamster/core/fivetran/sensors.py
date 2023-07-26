import json
import re

import pendulum
from dagster import (
    AssetKey,
    AssetsDefinition,
    AssetSelection,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)
from dagster_fivetran import FivetranResource
from dagster_gcp import BigQueryResource


def render_fivetran_audit_query(dataset, done):
    return f"""
        select distinct table
        from {dataset}.fivetran_audit
        where done >= '{done}'
    """


def build_fivetran_sync_monitor_sensor(
    code_location, asset_defs: list[AssetsDefinition], minimum_interval_seconds=None
):
    connectors = {}
    for asset in asset_defs:
        connector_id = re.match(
            pattern=r"fivetran_sync_(\w+)",
            string=asset.op.name,
        ).group(1)

        connectors[connector_id] = set(["_".join(key.path[1:-1]) for key in asset.keys])

    @sensor(
        name=f"{code_location}_fivetran_async_asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        asset_selection=AssetSelection.assets(*asset_defs),
    )
    def _sensor(
        context: SensorEvaluationContext,
        fivetran: FivetranResource,
        db_bigquery: BigQueryResource,
    ):
        cursor: dict = json.loads(s=(context.cursor or "{}"))
        bq = next(db_bigquery)

        asset_keys = []
        for connector_id, connector_schemas in connectors.items():
            # check if fivetran sync has completed
            last_update = pendulum.from_timestamp(cursor.get(connector_id, 0))

            (
                curr_last_sync_completion,
                curr_last_sync_succeeded,
                curr_sync_state,
            ) = fivetran.get_connector_sync_status(connector_id)

            context.log.info(
                (
                    f"Polled '{connector_id}'. "
                    f"Status: [{curr_sync_state}] @ {curr_last_sync_completion}"
                )
            )

            curr_last_sync_completion_timestamp = curr_last_sync_completion.timestamp()

            if (
                curr_last_sync_succeeded
                and curr_last_sync_completion_timestamp > last_update.timestamp()
            ):
                for schema in connector_schemas:
                    # get fivetran_audit table
                    query_job = bq.query(
                        query=render_fivetran_audit_query(
                            dataset=schema, done=last_update.to_iso8601_string()
                        )
                    )

                    for row in query_job.result():
                        asset_keys.append(AssetKey([code_location, schema, row.table]))

                cursor[connector_id] = curr_last_sync_completion_timestamp

        if asset_keys:
            return SensorResult(
                run_requests=[
                    RunRequest(
                        run_key=f"{context._sensor_name}_{pendulum.now().timestamp()}",
                        asset_selection=asset_keys,
                    )
                ],
                cursor=json.dumps(obj=cursor),
            )

    return _sensor
