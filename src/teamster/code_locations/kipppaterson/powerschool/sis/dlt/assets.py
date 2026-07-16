import pathlib

import yaml

from teamster.code_locations.kipppaterson import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import (
    build_powerschool_dlt_assets,
)

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"

assets = [
    build_powerschool_dlt_assets(
        code_location=CODE_LOCATION,
        table_name=a["table_name"],
        load_strategy=a["load_strategy"],
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
]
