from dagster import repository

from teamster.core.datagun import jobs as datagun_jobs_core
from teamster.core.powerschool.jobs import db as psdb_jobs_core
from teamster.core.powerschool.schedules import db as psdb_sched_core
from teamster.local.datagun import jobs as datagun_jobs_local
from teamster.local.datagun import schedules as datagun_schedules


@repository
def powerschool():
    jobs = [v for k, v in vars(psdb_jobs_core).items() if k in psdb_jobs_core.__all__]
    schedules = [
        v for k, v in vars(psdb_sched_core).items() if k in psdb_sched_core.__all__
    ]
    sensors = []

    return jobs + schedules + sensors


@repository
def datagun():
    core_jobs = [
        v for k, v in vars(datagun_jobs_core).items() if k in datagun_jobs_core.__all__
    ]
    local_jobs = [
        v
        for k, v in vars(datagun_jobs_local).items()
        if k in datagun_jobs_local.__all__
    ]
    jobs = core_jobs + local_jobs
    schedules = [
        v for k, v in vars(datagun_schedules).items() if k in datagun_schedules.__all__
    ]

    return jobs + schedules


__all__ = ["powerschool", "datagun"]
