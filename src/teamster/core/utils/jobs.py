from dagster import job

from teamster.core.utils.ops import asset_observation_op


@job
def asset_observation_job():
    asset_observation_op()


__all__ = [
    asset_observation_job,
]
