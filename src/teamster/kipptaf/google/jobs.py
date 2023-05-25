from dagster import job

from .. import CODE_LOCATION
from .ops import asset_observation_op


@job(name=f"{CODE_LOCATION}_gsheet_observation_job")
def asset_observation_job():
    asset_observation_op()


__all__ = [
    asset_observation_job,
]
