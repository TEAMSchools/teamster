from dagster import job

from teamster.core.airbyte.ops import airbyte_materialization_op


@job
def airbyte_materialization_job():
    airbyte_materialization_op()


__all__ = [
    airbyte_materialization_job,
]
