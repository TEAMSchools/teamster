import json
import time

from dagster import (
    AssetMaterialization,
    AssetSpec,
    SensorEvaluationContext,
    SensorResult,
    SkipReason,
    sensor,
)
from dagster_gcp import BigQueryResource
from google.cloud.bigquery import DatasetReference, TableReference
from google.cloud.bigquery.retry import DEFAULT_RETRY

from teamster import GCS_PROJECT_NAME
from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.airbyte.assets import (
    asset_specs as airbyte_asset_specs,
)
from teamster.code_locations.kipptaf.google.appsheet.assets import (
    asset_specs as google_appsheet_asset_specs,
)

asset_selection: list[AssetSpec] = [*google_appsheet_asset_specs, *airbyte_asset_specs]

# Wall-clock budget for one tick's polling loop. The tick is killed at 600s by
# default_sensor_timeout, and a single get_table below can burn ~30s before it
# gives up, so this leaves room for one in-flight call to finish past the check.
# Polling every asset normally takes a few seconds, so the budget only bites once
# BigQuery metadata calls start timing out -- at which point the loop stops and
# resumes on the next tick instead of running the whole tick into the timeout.
TICK_TIME_BUDGET_SECONDS = 300

# Cursor key holding the resume position. "$" is not legal in a Python
# identifier, so this can never collide with an AssetKey.to_python_identifier()
# entry sharing the same dict.
OFFSET_CURSOR_KEY = "$offset"


@sensor(
    name=f"{CODE_LOCATION}__google__bigquery__table_modified_sensor",
    minimum_interval_seconds=(60 * 5),
)
def bigquery_table_modified_sensor(
    context: SensorEvaluationContext, db_bigquery: BigQueryResource
):
    asset_events = []
    cursor: dict = json.loads(context.cursor or "{}")

    offset = cursor.get(OFFSET_CURSOR_KEY, 0)

    # tolerate a cursor written before this key existed, and an offset left
    # dangling by a deploy that shortened asset_selection. A deploy that REORDERS
    # asset_selection without changing its length is not detectable here: the
    # resumed tick polls a different slice than the one it skipped. That is
    # bounded and self-healing -- per-asset state is keyed by identifier rather
    # than index, so the worst case is one sweep's detection delay, never a lost
    # or duplicated materialization.
    if not isinstance(offset, int) or not 0 <= offset < len(asset_selection):
        offset = 0

    deadline = time.monotonic() + TICK_TIME_BUDGET_SECONDS

    # 0 means the sweep finished; a break below overwrites it with the resume index
    next_offset = 0

    with db_bigquery.get_client() as bq:
        for index in range(offset, len(asset_selection)):
            if time.monotonic() >= deadline:
                next_offset = index
                context.log.info(
                    msg=(
                        f"Tick time budget of {TICK_TIME_BUDGET_SECONDS}s exhausted "
                        f"after {index - offset} assets; resuming at index {index}"
                    )
                )
                break

            assets_def = asset_selection[index]
            python_identifier = assets_def.key.to_python_identifier()

            cursor_modified_timestamp = cursor.get(python_identifier, 0)

            table_ref = TableReference(
                dataset_ref=DatasetReference(
                    project=GCS_PROJECT_NAME,
                    dataset_id=assets_def.metadata["dataset_id"],
                ),
                table_id=assets_def.metadata["table_id"],
            )

            table = bq.get_table(
                table=table_ref,
                retry=DEFAULT_RETRY.with_deadline(30),
                timeout=10,
            )

            if table.modified is None:
                continue
            else:
                table_modified_timestamp = table.modified.timestamp()

            if table_modified_timestamp > cursor_modified_timestamp:
                context.log.info(msg=f"{assets_def.key}:\t{table_modified_timestamp}")
                asset_events.append(AssetMaterialization(asset_key=assets_def.key))
                cursor[python_identifier] = table_modified_timestamp

    cursor[OFFSET_CURSOR_KEY] = next_offset

    if asset_events:
        skip_reason = None
    elif next_offset:
        # a partial slice found nothing, but assets remain unpolled this sweep
        skip_reason = SkipReason(
            f"No modified tables in this slice; resuming at index {next_offset}."
        )
    else:
        skip_reason = SkipReason("No modified tables.")

    # the cursor is returned on every tick, not just ticks that emit events --
    # otherwise the resume offset would be discarded and the tail of
    # asset_selection would never be polled
    return SensorResult(
        asset_events=asset_events,
        cursor=json.dumps(obj=cursor),
        skip_reason=skip_reason,
    )


sensors = [
    bigquery_table_modified_sensor,
]
