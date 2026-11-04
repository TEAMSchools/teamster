from teamster.code_locations.kipppaterson import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipppaterson.finalsite.assets import contacts
from teamster.libraries.finalsite.api.schedules import (
    build_finalsite_contacts_schedule,
)

finalsite_contacts_daily_asset_job_schedule = build_finalsite_contacts_schedule(
    code_location=CODE_LOCATION,
    execution_timezone=str(LOCAL_TIMEZONE),
    asset_selection=[contacts],
)

schedules = [
    finalsite_contacts_daily_asset_job_schedule,
]
