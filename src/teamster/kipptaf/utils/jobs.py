from dagster import job

from teamster.core.utils.ops import asset_observation_op

from .. import CODE_LOCATION


@job(name=f"{CODE_LOCATION}_asset_observation_job")
def asset_observation_job():
    asset_observation_op()


__all__ = [
    asset_observation_job,
]
