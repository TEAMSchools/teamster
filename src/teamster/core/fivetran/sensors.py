import json

import pendulum
from dagster import (
    AssetKey,
    RunConfig,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    SourceAsset,
    sensor,
)
from dagster_fivetran import FivetranResource
from dagster_fivetran.resources import DEFAULT_POLL_INTERVAL
from dagster_gcp import BigQueryResource

from teamster.core.utils.jobs import asset_observation_job
from teamster.core.utils.ops import ObservationOpConfig


def render_fivetran_audit_query(dataset, done):
    return f"""
        select distinct table
        from {dataset}.fivetran_audit
        where done >= '{done}'
    """


def build_fivetran_sync_monitor_sensor(
    code_location, asset_defs: list[SourceAsset], minimum_interval_seconds=None
):
    connectors = {
        asset.metadata["connector_id"].value: asset.metadata["connector_name"].value
        for asset in asset_defs
    }

    @sensor(
        name=f"{code_location}_fivetran_async_asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
        job=asset_observation_job,
    )
    def _sensor(
        context: SensorEvaluationContext,
        fivetran: FivetranResource,
        db_bigquery: BigQueryResource,
    ):
        cursor: dict = json.loads(s=(context.cursor or "{}"))

        asset_keys = []
        for connector_id, connector_name in connectors.items():
            # check if fivetran sync has completed
            last_update = pendulum.from_timestamp(cursor.get(connector_name, 0))
            poll_start = pendulum.now()

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
                # get fivetran_audit table
                query_job = db_bigquery.query(
                    query=render_fivetran_audit_query(
                        dataset=connector_name, done=last_update.to_iso8601_string()
                    )
                )

                for row in query_job.result():
                    asset_keys.append(
                        AssetKey([code_location, connector_name, row.table])
                    )

                cursor[connector_name] = curr_last_sync_completion_timestamp

            now = pendulum.now()
            if now > poll_start.add(seconds=DEFAULT_POLL_INTERVAL):
                context.log.error(
                    f"Sync for connector '{connector_name}' timed out after "
                    f"{now - poll_start}."
                )

        if asset_keys:
            return SensorResult(
                run_requests=[
                    RunRequest(
                        run_key=f"{context._sensor_name}_{pendulum.now().timestamp()}",
                        run_config=RunConfig(
                            ops={
                                "asset_observation_op": ObservationOpConfig(
                                    asset_keys=asset_keys
                                )
                            }
                        ),
                    )
                ],
                cursor=json.dumps(obj=cursor),
            )

    return _sensor
