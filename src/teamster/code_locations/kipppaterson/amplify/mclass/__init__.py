from teamster.code_locations.kipppaterson.amplify.mclass import sftp

assets = [
    *sftp.assets,
]

sensors = [
    *sftp.sensors,
]

__all__ = [
    "assets",
    "sensors",
]
