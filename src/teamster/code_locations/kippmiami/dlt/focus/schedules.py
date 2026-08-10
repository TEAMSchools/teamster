import pathlib

import yaml
from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE

config_file = pathlib.Path(__file__).parent / "config" / "focus.yaml"
config = yaml.safe_load(config_file.read_text())

asset_key_prefix = f"{CODE_LOCATION}/dlt/focus"

# Only the count-only tables (no `cursor_column` -- as of writing, co_teachers
# and login_history) belong in this tier. Derived from config rather than
# hardcoded so a table that later loses its cursor joins automatically, and
# one that gains a real cursor drops out without a code change here.
daily_full_refresh_targets = [
    f"{asset_key_prefix}/{a['table_name']}"
    for a in config["assets"]
    if a["cursor_column"] is None
]

focus_dlt_daily_asset_job_schedule = ScheduleDefinition(
    # The name says "daily" but this tier now runs once a day, at 04:00 -- the
    # 12:00 and 14:00 crons moved to the intraday sensor below. The name is
    # kept as-is on purpose -- renaming mints a NEW Dagster+ schedule object
    # and abandons this one's status and tick history.
    name=f"{CODE_LOCATION}__dlt__focus__daily_asset_job_schedule",
    # This is the daily in-place-edit backstop for the tables whose
    # `cursor_column` is null: a count+cursor probe can't see an edit that
    # leaves row count unchanged on a table with no `updated_at` (or
    # equivalent) to bump, so those tables instead get an unconditional daily
    # reload. Everything else has a verified-reliable `updated_at`
    # (`docs/superpowers/specs/2026-08-10-focus-dlt-probe-gated-sync-design.md`),
    # so `kippmiami__dlt__focus__intraday_sensor` fully gates it and this tier
    # no longer touches it -- the sensor still probes all 77 tables every 15
    # minutes and catches adds/removes on the count-only ones too, just not a
    # silent in-place edit.
    #
    # This tier is NOT the pre-dawn full refresh Focus-derived models
    # (Miami enrollment, attendance, the FRESH scaffold) depend on anymore --
    # that data comes from `updated_at`-tracked tables the sensor keeps fresh
    # continuously, not from here. Losing this tier delays an in-place edit to
    # a count-only table by up to a day; it has no effect on FRESH's 05:00
    # Tableau extract or the 12:45 delivery.
    cron_schedule="0 4 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
    target=daily_full_refresh_targets,
    # The sensor's in-flight guard (probe.py::in_flight_run) skips every tick
    # while a run launched by this schedule is non-terminal, so a hung run
    # here can still wedge intraday syncing. 900 is deliberate, not copied:
    # this tier now loads two small tables (100s of rows, not 77), so the
    # bound isn't sized to load time anymore -- it's sized to roughly one
    # sensor interval (900s), so a hung run can't wedge intraday syncing for
    # longer than about one tick.
    tags={"dagster/max_runtime": "900"},
)

schedules = [focus_dlt_daily_asset_job_schedule]
