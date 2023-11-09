from teamster.core.airbyte.sensors import build_airbyte_job_status_sensor

from . import assets

airbyte_job_status_sensor = build_airbyte_job_status_sensor(
    asset_defs=assets, minimum_interval_seconds=(60 * 1)
)

__all__ = [
    airbyte_job_status_sensor,
]
