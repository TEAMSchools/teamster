import json
import re

import pendulum
from dagster import SensorEvaluationContext, SensorResult, sensor
from dagster_fivetran import FivetranResource
from dagster_fivetran.resources import DEFAULT_POLL_INTERVAL

from . import assets


def build_fivetran_async_asset_sensor(asset_defs, minimum_interval_seconds=None):
    @sensor(
        name="fivetran_async_asset_sensor",
        minimum_interval_seconds=minimum_interval_seconds,
    )
    def _sensor(context: SensorEvaluationContext, fivetran: FivetranResource):
        cursor: dict = json.loads(s=(context.cursor or "{}"))

        for asset_def in asset_defs:
            connector_id = re.match(
                pattern=r"fivetran_sync_(?P<connector_id>\w+)",
                string=asset_def.node_def.name,
            ).groupdict()["connector_id"]

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
                and curr_last_sync_completion_timestamp > cursor.get(connector_id, 0)
            ):
                # TODO: materialize assets
                ...

                cursor[connector_id] = curr_last_sync_completion_timestamp

            now = pendulum.now()
            if now > poll_start.add(seconds=DEFAULT_POLL_INTERVAL):
                context.log.error(
                    f"Sync for connector '{connector_id}' timed out after "
                    f"{now - poll_start}."
                )

        return SensorResult(cursor=json.dumps(obj=cursor))

    return _sensor


fivetran_async_asset_sensor = build_fivetran_async_asset_sensor(asset_defs=assets)

__all__ = [
    fivetran_async_asset_sensor,
]
