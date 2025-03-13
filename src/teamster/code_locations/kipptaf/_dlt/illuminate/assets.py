import pathlib

import yaml
from dagster import EnvVar, _check
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.dlt.illuminate.assets import build_illuminate_dlt_assets

config_file = pathlib.Path(__file__).parent / "config" / "illuminate.yaml"

sql_database_credentials = ConnectionStringCredentials(
    {
        "drivername": _check.not_none(
            value=EnvVar("ILLUMINATE_DB_DRIVERNAME").get_value()
        ),
        "database": EnvVar("ILLUMINATE_DB_DATABASE").get_value(),
        "password": EnvVar("ILLUMINATE_DB_PASSWORD").get_value(),
        "username": EnvVar("ILLUMINATE_DB_USERNAME").get_value(),
        "host": EnvVar("ILLUMINATE_DB_HOST").get_value(),
    }
)

assets = [
    build_illuminate_dlt_assets(
        sql_database_credentials=sql_database_credentials,
        code_location=CODE_LOCATION,
        schema=a["schema"],
        **t,
    )
    for a in yaml.safe_load(config_file.read_text())["assets"]
    for t in a["tables"]
]
