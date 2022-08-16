from dagster import repository

from teamster.local.jobs import datagun as datagun_jobs
from teamster.local.schedules import datagun as datagun_schedules


@repository
def datagun():
    jobs = [v for k, v in vars(datagun_jobs).items() if k in datagun_jobs.__all__]
    schedules = [
        v for k, v in vars(datagun_schedules).items() if k in datagun_schedules.__all__
    ]

    return jobs + schedules


__all__ = ["datagun"]
