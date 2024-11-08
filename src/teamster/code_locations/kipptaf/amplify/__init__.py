from teamster.code_locations.kipptaf.amplify import dibels, mclass

assets = [
    *dibels.assets,
    *mclass.assets,
]

schedules = [
    *dibels.schedules,
    *mclass.schedules,
]

__all__ = [
    "assets",
    "schedules",
]
