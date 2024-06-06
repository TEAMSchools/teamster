from teamster.code_locations.kipptaf.adp.workforce_now import api, sftp

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

__all__ = [
    "assets",
    "jobs",
    "schedules",
    "sensors",
]
