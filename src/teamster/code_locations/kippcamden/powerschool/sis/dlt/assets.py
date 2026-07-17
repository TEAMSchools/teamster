import pathlib

import yaml

from teamster.code_locations.kippcamden import CODE_LOCATION
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
        # dlt's default extract concurrency (5 workers). The single SSH tunnel
        # no longer caps volume: the earlier DPY-4011 was a paramiko rekey
        # failure at 512 MiB, not tunnel saturation, and is fixed in
        # SSHResource. A per-run `dlt_extract_workers` tag still overrides this
        # for ad-hoc tuning.
    )
]
