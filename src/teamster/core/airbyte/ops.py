from dagster import OpExecutionContext, op
from dagster_airbyte.utils import generate_materializations


@op
def foo(context: OpExecutionContext, config: ...):
    for job in config.jobs:
        yield from generate_materializations(
            output=job.airbyte_output, asset_key_prefix=job.asset_key_prefix
        )
