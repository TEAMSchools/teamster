from teamster.core.airbyte.sensors import build_airbyte_job_status_sensor

from .jobs import airbyte_materialization_job

airbyte_job_status_sensor = build_airbyte_job_status_sensor(
    job=airbyte_materialization_job
)

__all__ = [
    airbyte_job_status_sensor,
]
