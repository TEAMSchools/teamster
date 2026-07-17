from teamster.code_locations.kippnewark.powerschool import sis
from teamster.code_locations.kippnewark.powerschool.assets import assets as odbc_assets
from teamster.code_locations.kippnewark.powerschool.schedules import schedules
from teamster.code_locations.kippnewark.powerschool.sensors import sensors

assets = [*odbc_assets, *sis.assets]

__all__ = [
    "assets",
    "schedules",
    "sensors",
]
