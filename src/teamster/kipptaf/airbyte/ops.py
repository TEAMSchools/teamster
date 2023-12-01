# forked from dagster_airbyte.ops and dagster_airbyte.resources
from typing import Iterable, cast

from dagster import Any, Dict, In, Nothing, OpExecutionContext, Out, op
from dagster_airbyte import AirbyteOutput
from dagster_airbyte.ops import AirbyteSyncConfig
from dagster_airbyte.resources import BaseAirbyteResource


@op(
    ins={"start_after": In(Nothing)},
    out=Out(
        AirbyteOutput,
        description=(
            "Parsed json dictionary representing the details of the Airbyte connector "
            "after the sync successfully completes. See the [Airbyte API Docs](https://"
            "airbyte-public-api-docs.s3.us-east-2.amazonaws.com/rapidoc-api-docs."
            "html#overview) to see detailed information on this response."
        ),
    ),
    tags={"kind": "airbyte"},
)
def airbyte_start_sync_op(
    context: OpExecutionContext, config: AirbyteSyncConfig, airbyte: BaseAirbyteResource
) -> Iterable[Any]:
    job_details = airbyte.start_sync(config.connection_id)

    job_info = cast(Dict[str, object], job_details.get("job", {}))

    job_id = cast(int, job_info.get("id"))

    context.log.info(
        f"Job {job_id} initialized for connection_id={config.connection_id}."
    )

    return AirbyteOutput(
        job_details=job_details,
        connection_details=airbyte.get_connection_details(config.connection_id),
    )
