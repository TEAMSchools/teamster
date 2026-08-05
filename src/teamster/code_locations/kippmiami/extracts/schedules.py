from dagster import ScheduleDefinition

from teamster.code_locations.kippmiami import LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.extracts.jobs import focus_extract_asset_job

focus_extract_assets_schedule = ScheduleDefinition(
    job=focus_extract_asset_job,
    # Delivers the four Focus import CSVs to the Focus SFTP `incoming/` folder.
    # Enrollment ops run the Focus imports BY HAND, and leadership commits to
    # stakeholders that a student entered in Finalsite by 12:00pm ET is usable in
    # Focus by 2:00pm ET -- so this lands at 12:30pm. The hand-run imports are
    # quick, so the 90 min before 2pm is slack rather than a window being consumed;
    # 12:30 is chosen for EARLIER usability, not to make room for the imports.
    # Upstreams all run concurrently at 12:00 (nothing about them is sequential):
    # the manual Finalsite SFTP push, the Finalsite contacts pull, the Focus dlt
    # pull, and the dbt rebuild the automation-condition sensor fires off each.
    #
    # NOTHING GATES THIS ON THOSE UPSTREAMS -- it is a plain cron, so the gap is a
    # time budget, not a dependency. The binding term is the manual SFTP push, not
    # any ordering between Finalsite and Focus: worst case ~16 min from push to
    # rebuilt (10 min couchdrop sensor poll + 2 min ingest + 3.5 min dbt). The
    # scheduled pulls need only 4-7 min. So the push deadline is always this time
    # minus ~16 min -- currently ~12:14, i.e. 14 min after the noon cutoff. Moving
    # this LATER is the only lever that buys ops more push tolerance, and there is
    # ~90 min of slack before 2pm to spend if they turn out to need it. Anything
    # before ~12:16 makes the push deadline land before noon, which contradicts the
    # "entered by 12:00" promise outright.
    cron_schedule="30 12 * * *",
    execution_timezone=str(LOCAL_TIMEZONE),
)

schedules = [
    focus_extract_assets_schedule,
]
