import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"
config = yaml.safe_load(config_file.read_text())

asset_key_prefix = f"{CODE_LOCATION}/dlt/focus"

focus_dlt_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule",
    cron_schedule="0 0 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{asset_key_prefix}/{a['table_name']}" for a in config["assets"]],
)

schedules = [focus_dlt_daily_asset_job_schedule]
