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
    # This is now the UNCONDITIONAL full-refresh tier. The 12:00 and 14:00 crons
    # were replaced by `kippmiami__dlt__focus__intraday_sensor`, which probes
    # every table every 15 minutes and loads only the drifted ones -- so the
    # live-Focus snapshot the rpt_focus__* import-once anti-joins read is
    # refreshed within 15 minutes of a change instead of at two fixed times. The
    # safe rule for ops is unchanged and is a dependency, not a clock time: do
    # not re-run the delivery unless a Focus sync has run SINCE the last import.
    #
    # Keep this tier unconditional. It is the backstop for any table whose
    # `updated_at` the Focus app does not bump on an in-place edit, which the
    # count+cursor probe cannot see.
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{asset_key_prefix}/{a['table_name']}" for a in config["assets"]],
)

schedules = [focus_dlt_daily_asset_job_schedule]
