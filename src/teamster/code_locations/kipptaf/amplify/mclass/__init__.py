from teamster.code_locations.kipptaf.amplify.mclass import sftp

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
