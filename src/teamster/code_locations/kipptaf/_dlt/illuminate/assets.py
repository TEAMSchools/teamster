import pathlib

import yaml

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.dlt.illuminate.assets import build_illuminate_dlt_assets

config_file = pathlib.Path(__file__).parent / "config" / "illuminate.yaml"

assets = [
    build_illuminate_dlt_assets(code_location=CODE_LOCATION, schema=a["schema"], **t)
    for a in yaml.safe_load(config_file.read_text())["assets"]
    for t in a["tables"]
]
