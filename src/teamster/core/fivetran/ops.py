# forked from dagster_fivetran/ops.py
from typing import Any, Mapping

from dagster import In, Nothing, Out, Output, op
from dagster_fivetran import FivetranResource
from dagster_fivetran.ops import FivetranResyncConfig, SyncConfig


@op(
    ins={"start_after": In(Nothing)},
    out=Out(
        Mapping[str, Any],
        description=(
            "Parsed json data representing the connector details API response after "
            "the sync is started."
        ),
    ),
    tags={"kind": "fivetran"},
)
def fivetran_sync_op(config: SyncConfig, fivetran: FivetranResource) -> Any:
    fivetran_output = fivetran.start_sync(connector_id=config.connector_id)

    yield Output(fivetran_output)


@op(
    ins={"start_after": In(Nothing)},
    out=Out(
        Mapping[str, Any],
        description=(
            "Parsed json data representing the connector details API response after "
            "the sync is started."
        ),
    ),
    tags={"kind": "fivetran"},
)
def fivetran_resync_op(
    config: FivetranResyncConfig,
    fivetran: FivetranResource,
) -> Any:
    fivetran_output = fivetran.start_resync(
        connector_id=config.connector_id, resync_parameters=config.resync_parameters
    )

    yield Output(fivetran_output)
