from . import payroll, workforce_manager, workforce_now

assets = [
    *payroll.assets,
    *workforce_manager.assets,
    *workforce_now.assets,
]

jobs = [
    *workforce_manager.jobs,
    *workforce_now.jobs,
]

schedules = [
    *workforce_manager.schedules,
    *workforce_now.schedules,
]

sensors = [
    *payroll.sensors,
    *workforce_now.sensors,
]

_all = [
    assets,
    jobs,
    schedules,
    sensors,
]
