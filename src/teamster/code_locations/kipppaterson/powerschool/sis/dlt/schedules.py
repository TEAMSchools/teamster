import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"
config = yaml.safe_load(config_file.read_text())


def _tier_targets(tier: str) -> list[str]:
    return [
        f"{CODE_LOCATION}/powerschool/{a['table_name']}"
        for a in config["assets"]
        if a["schedule_tier"] == tier
    ]


powerschool_dlt_intraday_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__intraday_asset_job_schedule",
    cron_schedule="*/15 * * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_tier_targets("intraday"),
)

powerschool_dlt_nightly_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule",
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_tier_targets("nightly"),
)

schedules = [
    powerschool_dlt_intraday_asset_job_schedule,
    powerschool_dlt_nightly_asset_job_schedule,
]
