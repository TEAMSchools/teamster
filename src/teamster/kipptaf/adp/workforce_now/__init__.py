from .api.jobs import _all as jobs
from .api.schedules import _all as schedules
from .sftp.assets import _all as assets
from .sftp.sensors import _all as sensors

_all = [
    assets,
    jobs,
    schedules,
    sensors,
]
