import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kippcamden import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "assets.yaml"
config = yaml.safe_load(config_file.read_text())


def _nightly_targets() -> list[str]:
    assets = config["assets"]

    orphaned = [a["table_name"] for a in assets if not (a["intraday"] or a["nightly"])]
    if orphaned:
        raise ValueError(
            "table(s) in neither tier (would never materialize): " + ", ".join(orphaned)
        )

    return [
        f"{CODE_LOCATION}/powerschool/sis/{a['table_name']}"
        for a in assets
        if a["nightly"]
    ]


# Unconditional full refresh + re-baseline (the op's no-probe mode): the
# authoritative sweep that catches in-place edits the intraday count gate
# cannot see on no-cursor tables.
powerschool_dlt_nightly_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__powerschool__dlt__nightly_asset_job_schedule",
    cron_schedule="0 2 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=_nightly_targets(),
    tags={"dagster/max_runtime": "3600"},
)

schedules = [powerschool_dlt_nightly_asset_job_schedule]
