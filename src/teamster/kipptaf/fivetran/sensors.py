import json
import re

import pendulum
from dagster import (
    AssetSelection,
    MultiAssetSensorEvaluationContext,
    SensorResult,
    multi_asset_sensor,
)
from dagster_fivetran import FivetranResource
from dagster_fivetran.resources import DEFAULT_POLL_INTERVAL

from . import assets


@multi_asset_sensor(
    monitored_assets=AssetSelection.assets(*assets),
    # minimum_interval_seconds=(60 * 10),
)
def fivetran_async_asset_sensor(
    context: MultiAssetSensorEvaluationContext, fivetran: FivetranResource
):
    cursor: dict = json.loads(context.cursor or "{}")

    asset_defs = set()
    for asset_key, asset_def in context.assets_defs_by_key.items():
        asset_defs.add(asset_def)

    context.log.debug(asset_defs)
    for asset_def in asset_defs:
        poll_start = pendulum.now()

        connector_id = re.match(
            pattern=r"fivetran_sync_(?P<connector_id>\w+)",
            string=asset_def.node_def.name,
        ).groupdict()["connector_id"]

        (
            curr_last_sync_completion,
            curr_last_sync_succeeded,
            curr_sync_state,
        ) = fivetran.get_connector_sync_status(connector_id)
        context.log.info(f"Polled '{connector_id}'. Status: [{curr_sync_state}]")

        curr_last_sync_completion_timestamp = curr_last_sync_completion.timestamp()

        if (
            curr_last_sync_succeeded
            and curr_last_sync_completion_timestamp > cursor.get(connector_id, 0)
        ):
            # ...  # materialize assets
            cursor[connector_id] = curr_last_sync_completion_timestamp

        now = pendulum.now()
        if now > poll_start.add(seconds=DEFAULT_POLL_INTERVAL):
            context.log.error(
                f"Sync for connector '{connector_id}' timed out after "
                f"{now - poll_start}."
            )

    return SensorResult(cursor=cursor)


__all__ = [
    fivetran_async_asset_sensor,
]
