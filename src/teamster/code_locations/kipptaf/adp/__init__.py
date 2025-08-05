from teamster.code_locations.kipptaf.adp import payroll, workforce_now

assets = [
    *payroll.assets,
    *workforce_now.assets,
]

schedules = [
    *workforce_now.schedules,
]

sensors = [
    *workforce_now.sensors,
    *payroll.sensors,
]

__all__ = [
    "assets",
    "schedules",
    "sensors",
]
