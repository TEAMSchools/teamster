import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"
config = yaml.safe_load(config_file.read_text())

_VALID_SCHEDULE_TIERS = {"intraday", "nightly"}


def _tier_targets(tier: str) -> list[str]:
    assets = config["assets"]

    invalid = [a for a in assets if a["schedule_tier"] not in _VALID_SCHEDULE_TIERS]
    if invalid:
        raise ValueError(
            "Invalid schedule_tier for table(s): "
            + ", ".join(
                f"{a['table_name']!r} ({a['schedule_tier']!r})" for a in invalid
            )
            + f"; expected one of {sorted(_VALID_SCHEDULE_TIERS)}"
        )

    if tier == "intraday":
        # no-cursor tables cannot be probe-gated, so they must not run intraday
        ungated = [
            a
            for a in assets
            if a["schedule_tier"] == "intraday" and a["cursor_column"] is None
        ]
        if ungated:
            raise ValueError(
                "intraday tables require a cursor_column: "
                + ", ".join(a["table_name"] for a in ungated)
            )

    return [
        f"{CODE_LOCATION}/powerschool/sis/{a['table_name']}"
        for a in assets
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
