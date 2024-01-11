# based on dagster_airbyte.resources.BaseAirbyteResource.sync_and_poll
from typing import Any, Dict, Iterable, cast

from dagster import In, Nothing, OpExecutionContext, Out, op
from dagster_airbyte import AirbyteCloudResource, AirbyteOutput
from dagster_airbyte.ops import AirbyteSyncConfig


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
    context: OpExecutionContext,
    config: AirbyteSyncConfig,
    airbyte: AirbyteCloudResource,
) -> Iterable[Any]:
    job_details = airbyte.start_sync(config.connection_id)
    connection_details = airbyte.get_connection_details(config.connection_id)

    job_info = cast(Dict[str, object], job_details.get("job", {}))

    job_id = cast(int, job_info.get("id"))

    context.log.info(
        f"Job {job_id} initialized for connection_id={config.connection_id}."
    )

    return AirbyteOutput(job_details=job_details, connection_details=connection_details)
