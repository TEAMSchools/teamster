from dagster import repository

from teamster.kippmiami.jobs import datagun as datagun_jobs
from teamster.kippmiami.jobs.powerschool import db as ps_db_jobs
from teamster.kippmiami.schedules import datagun as datagun_schedules

# from teamster.kippmiami.schedules.powerschool import db as ps_db_schedules


@repository
def powerschool():
    jobs = [v for k, v in vars(ps_db_jobs).items() if k in ps_db_jobs.__all__]
    # schedules = [
    #   v for k, v in vars(ps_schedules).items() if k in ps_schedules.__all__
    # ]
    schedules = []
    sensors = []

    return jobs + schedules + sensors


@repository
def datagun():
    jobs = [v for k, v in vars(datagun_jobs).items() if k in datagun_jobs.__all__]
    schedules = [
        v for k, v in vars(datagun_schedules).items() if k in datagun_schedules.__all__
    ]

    return jobs + schedules


__all__ = ["powerschool", "datagun"]
