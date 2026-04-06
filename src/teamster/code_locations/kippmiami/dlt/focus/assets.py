import pathlib

import yaml
from dlt.common.configuration import resolve_configuration
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = resolve_configuration(
    ConnectionStringCredentials(), sections=("FOCUS_DB",)
)

assets = [
    build_focus_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        **a,
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
]
