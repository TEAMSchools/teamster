from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.finalsite.assets import contacts
from teamster.libraries.finalsite.api.schedules import (
    build_finalsite_contacts_schedule,
)

finalsite_contacts_daily_asset_job_schedule = build_finalsite_contacts_schedule(
    code_location=CODE_LOCATION,
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=[contacts],
    # 12:00 feeds the midday Focus import cycle, firing alongside the Focus dlt
    # pull rather than staggered behind it: they share no pool and neither gates
    # the other (this API pull and the manually-pushed SFTP drop feed opposite
    # sides of int_finalsite__enrollment_lifecycle; the dlt pull feeds the
    # import-once anti-join). The 13:15 delivery is a plain cron with a 75-minute
    # time budget, not a dependency -- an incremental pull uses ~1-2 min of it
    # where the full snapshot used ~5. 00:15 replaces the old 04:00: FRESH's 05:00
    # Tableau extract still reads a same-day pull, and the NJ consumers at 01:00
    # and 01:25 stop reading yesterday's. See #4715.
    #
    # Miami used to be the ONLY district on a midday tick, so the finalsite_api
    # pool (limit 1) was uncontended at 12:00. All four now share it. That is
    # still comfortably inside the budget: four INCREMENTAL pulls serialized is
    # ~6 min against the 75 min before the 13:15 delivery, where four full
    # snapshots would have been ~46 min.
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
