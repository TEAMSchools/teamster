import pathlib

import yaml

from teamster.code_locations.kippnewark import CODE_LOCATION
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
        # Single-stream extract avoids saturating the one SSH tunnel (dlt's
        # default of 5 concurrent workers drops the Oracle connection,
        # DPY-4011). A per-run `dlt_extract_workers` tag overrides this for a
        # manual concurrency sweep.
        max_extract_workers=1,
    )
]
