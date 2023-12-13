from dagster import job

from teamster.core.utils.ops import asset_observation_op


@job(tags={"job_type": "op"})
def asset_observation_job():
    asset_observation_op()


_all = [
    asset_observation_job,
]
