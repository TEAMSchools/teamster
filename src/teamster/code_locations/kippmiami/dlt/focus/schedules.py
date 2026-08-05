import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"
config = yaml.safe_load(config_file.read_text())

asset_key_prefix = f"{CODE_LOCATION}/dlt/focus"

focus_dlt_daily_asset_job_schedule = ScheduleDefinition(
    name=f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule",
    # 04:00 keeps the pre-dawn pull that every Focus-derived model depends on --
    # Miami enrollment, attendance, and the FRESH scaffold's Miami rows all read
    # it, and FRESH's Tableau extract refreshes at 05:00. 12:25 refreshes the
    # live-Focus state that the rpt_focus__* import-once anti-joins compare
    # against, before the 12:45 delivery. 14:45 captures what enrollment ops
    # imported by hand: import-once is enforced against THIS snapshot, not live
    # Focus, so without a post-import pull a same-day re-run of the delivery
    # would re-send every record and duplicate it in Focus.
    cron_schedule=["0 4 * * *", "25 12 * * *", "45 14 * * *"],
    execution_timezone=str(LOCAL_TIMEZONE),
    target=[f"{asset_key_prefix}/{a['table_name']}" for a in config["assets"]],
)

schedules = [focus_dlt_daily_asset_job_schedule]
