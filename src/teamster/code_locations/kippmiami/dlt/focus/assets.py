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

widen_numeric_tables = frozenset(
    a["table_name"] for a in config_assets if a.get("widen_unbounded_numeric")
)
"""Tables whose unbounded Postgres `numeric` columns need an explicit scale.

`.get()`, not `[...]`: this key is absent on all but the tables that need it.
Opt-in rather than source-wide because widening retypes the column to BigQuery
BIGNUMERIC, and 45 already-loaded Focus tables carry 200 NUMERIC columns that
`replace` cannot retype in place.
"""

assets = [
    build_focus_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        tables=tables,
        widen_numeric_tables=widen_numeric_tables,
    )
]
