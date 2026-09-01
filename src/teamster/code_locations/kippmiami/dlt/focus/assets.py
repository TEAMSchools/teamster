import pathlib

import yaml
from dlt.common.configuration import resolve_configuration
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets
from teamster.libraries.dlt.probe import ProbeTable

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = resolve_configuration(
    ConnectionStringCredentials(), sections=("FOCUS_DB",)
)

config_assets = yaml.safe_load(config_file.read_text())["assets"]

tables = [
    # a["cursor_column"], not .get(): a new table added without a declared
    # cursor must fail loudly at module load, not silently become count-only.
    ProbeTable(name=a["table_name"], cursor_column=a["cursor_column"])
    for a in config_assets
]

"""Module-level so sensors.py can import it instead of re-parsing the YAML.

Keeps the credential resolution and config parse to one copy per code-location
import — both `assets.py` and `sensors.py` load unconditionally via
`dlt/focus/__init__.py`.
"""

assets = [
    build_focus_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        tables=tables,
    )
]
