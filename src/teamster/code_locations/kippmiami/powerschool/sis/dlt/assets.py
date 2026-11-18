import pathlib

import yaml

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.powerschool.assets import build_powerschool_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"

# Miami's PowerSchool is retired; these assets exist to rebuild the frozen
# kippmiami_powerschool archive and run only when launched by hand. They load
# only while `powerschool` is in definitions.py's modules list.
assets = [
    build_powerschool_dlt_assets(
        code_location=CODE_LOCATION,
        tables=[
            ProbeTable(name=a["table_name"], cursor_column=a["cursor_column"])
            for a in yaml.safe_load(config_file.read_text())["assets"]
        ],
    )
]
