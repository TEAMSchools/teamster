import pathlib

import yaml
from dlt.common.configuration import resolve_configuration
from dlt.common.configuration.specs import ConnectionStringCredentials

from teamster.code_locations.kippmiami import CODE_LOCATION
from teamster.libraries.dlt.focus.sensors import build_focus_dlt_intraday_sensor
from teamster.libraries.dlt.probe import ProbeTable

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"

sql_database_credentials = resolve_configuration(
    ConnectionStringCredentials(), sections=("FOCUS_DB",)
)

sensors = [
    build_focus_dlt_intraday_sensor(
        code_location=CODE_LOCATION,
        tables=[
            ProbeTable(name=a["table_name"], cursor_column=a["cursor_column"])
            for a in yaml.safe_load(config_file.read_text())["assets"]
        ],
        sql_database_credentials=sql_database_credentials,
        # Must match the schedule's `name` exactly — the in-flight guard reads
        # the `dagster/schedule_name` run tag.
        nightly_schedule_name=(
            f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule"
        ),
    )
]
