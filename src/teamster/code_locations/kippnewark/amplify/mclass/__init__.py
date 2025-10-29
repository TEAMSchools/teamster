from teamster.code_locations.kippnewark.amplify.mclass import sftp

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
