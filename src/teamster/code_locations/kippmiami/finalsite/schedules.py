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
    # the other. The 12:45 delivery is a plain cron with a 45-minute time
    # budget, not a dependency -- an incremental pull uses ~1-2 min of it where
    # the full snapshot used ~5. 00:15 replaces the old 04:00: FRESH's 05:00
    # Tableau extract still reads a same-day pull, and the NJ consumers at 01:00
    # and 01:25 stop reading yesterday's. See #4715.
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
