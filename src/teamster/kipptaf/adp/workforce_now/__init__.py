from . import api, sftp

assets = [
    *api.assets,
    *sftp.assets,
]

jobs = [
    *api.jobs,
]

schedules = [
    *api.schedules,
]

sensors = [
    *sftp.sensors,
]

_all = [
    assets,
    jobs,
    schedules,
    sensors,
]
