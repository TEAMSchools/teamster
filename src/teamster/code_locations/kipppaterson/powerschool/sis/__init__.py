from teamster.code_locations.kipppaterson.powerschool.sis import dlt, sftp

assets = [*dlt.assets.assets, *sftp.assets]

schedules = [*dlt.schedules.schedules]

__all__ = [
    "assets",
    "schedules",
]
