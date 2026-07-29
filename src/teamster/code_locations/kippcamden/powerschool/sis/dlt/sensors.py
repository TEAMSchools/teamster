import pathlib

import yaml

from teamster.code_locations.kippcamden import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import PowerSchoolTable
from teamster.libraries.dlt.powerschool.sensors import (
    build_powerschool_dlt_intraday_sensor,
)

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"

sensors = [
    build_powerschool_dlt_intraday_sensor(
        code_location=CODE_LOCATION,
        tables=[
            PowerSchoolTable(name=a["table_name"], cursor_column=a["cursor_column"])
            for a in yaml.safe_load(config_file.read_text())["assets"]
            if a["intraday"]
        ],
        nightly_schedule_name=(
            f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule"
        ),
    )
]
