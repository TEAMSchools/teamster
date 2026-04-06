import pathlib

import yaml
from dagster import EnvVar
from dagster_shared import check
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.assets import build_focus_dlt_assets

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = ConnectionStringCredentials(
    {
        "drivername": check.not_none(value=EnvVar("FOCUS_DB_DRIVERNAME").get_value()),
        "database": EnvVar("FOCUS_DB_DATABASE").get_value(),
        "password": EnvVar("FOCUS_DB_PASSWORD").get_value(),
        "username": EnvVar("FOCUS_DB_USERNAME").get_value(),
        "host": EnvVar("FOCUS_DB_HOST").get_value(),
        "port": EnvVar("FOCUS_DB_PORT").get_value(),
    }
)

assets = [
    build_focus_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        **a,
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
]
