import pathlib

import yaml

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import (
    PowerSchoolTable,
    build_powerschool_dlt_assets,
)

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"

assets = [
    build_powerschool_dlt_assets(
        code_location=CODE_LOCATION,
        tables=[
            PowerSchoolTable(name=a["table_name"], cursor_column=a["cursor_column"])
            for a in yaml.safe_load(config_file.read_text())["assets"]
        ],
    )
]
