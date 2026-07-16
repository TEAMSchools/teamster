import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"
config = yaml.safe_load(config_file.read_text())

_VALID_SCHEDULE_TIERS = {"intraday", "nightly"}

_invalid_tier_assets = [
    a for a in config["assets"] if a["schedule_tier"] not in _VALID_SCHEDULE_TIERS
]
if _invalid_tier_assets:
    raise ValueError(
        "Invalid schedule_tier for table(s): "
        + ", ".join(
            f"{a['table_name']!r} ({a['schedule_tier']!r})"
            for a in _invalid_tier_assets
        )
        + f"; expected one of {sorted(_VALID_SCHEDULE_TIERS)}"
    )

# no-cursor tables cannot be probe-gated, so they must not run intraday
_ungated_intraday = [
    a
    for a in config["assets"]
    if a["schedule_tier"] == "intraday" and a["cursor_column"] is None
]
if _ungated_intraday:
    raise ValueError(
        "intraday tables require a cursor_column: "
        + ", ".join(a["table_name"] for a in _ungated_intraday)
    )


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
    tags={"dagster/max_runtime": "3600"},
)

powerschool_dlt_nightly_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule",
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_tier_targets("nightly"),
    tags={"dagster/max_runtime": "3600"},
)

schedules = [
    powerschool_dlt_intraday_asset_job_schedule,
    powerschool_dlt_nightly_asset_job_schedule,
]
