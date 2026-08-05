import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"
config = yaml.safe_load(config_file.read_text())

asset_key_prefix = f"{CODE_LOCATION}/dlt/focus"

focus_dlt_daily_asset_job_schedule = ScheduleDefinition(
    # "daily" is now three times a day. The name is kept as-is on purpose --
    # renaming mints a NEW Dagster+ schedule object and abandons this one's
    # status and tick history.
    name=f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule",
    # 04:00 keeps the pre-dawn pull that every Focus-derived model depends on --
    # Miami enrollment, attendance, and the FRESH scaffold's Miami rows all read
    # it, and FRESH's Tableau extract refreshes at 05:00.
    #
    # 12:05 and 14:45 both refresh the live-Focus snapshot that the rpt_focus__*
    # import-once anti-joins read; a snapshot older than the last hand-run Focus
    # import makes the next delivery re-send those records and duplicate them in
    # Focus. Three snapshots a day means any one of them prevents that -- 14:45
    # catches the same-day imports, 04:00 is the overnight backstop, and 12:05 is
    # the last line of defence if both failed.
    #
    # 12:05 fires alongside the Finalsite contacts pull, not staggered behind it:
    # they share no pool and neither gates the other. That matters because the
    # 12:45 delivery is a plain cron with nothing gating it on this pull
    # finishing. Observed fire-to-stg_focus latency is 4-7 min against 40 min of
    # budget. Do not narrow that gap. 12:05 rather than 12:00 avoids top-of-hour
    # GKE Autopilot step-pod scheduling waits.
    cron_schedule=["0 4 * * *", "5 12 * * *", "45 14 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{asset_key_prefix}/{a['table_name']}" for a in config["assets"]],
)

schedules = [focus_dlt_daily_asset_job_schedule]
