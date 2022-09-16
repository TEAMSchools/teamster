from dagster import repository

from teamster.core.jobs import datagun as datagun_jobs_core
from teamster.local.schedules import datagun as datagun_schedules

# from teamster.core.jobs.powerschool import db as psdb_jobs_core

# @repository
# def powerschool():
#     jobs = [v for k, v in vars(psdb_jobs_core).items() if k in psdb_jobs_core.__all__]
#     schedules = []
#     sensors = []

#     return jobs + schedules + sensors


@repository
def datagun():
    jobs = [
        v for k, v in vars(datagun_jobs_core).items() if k in datagun_jobs_core.__all__
    ]
    schedules = [
        v for k, v in vars(datagun_schedules).items() if k in datagun_schedules.__all__
    ]

    return jobs + schedules


__all__ = [
    # "powerschool",
    "datagun"
]
