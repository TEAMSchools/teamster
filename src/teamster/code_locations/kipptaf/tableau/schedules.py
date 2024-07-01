from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.assets import external_assets, workbook
from teamster.libraries.tableau.schedules import (
    build_tableau_workbook_asset_job_schedule,
    build_tableau_workbook_refresh_schedule,
)

tableau_workbook_asset_job_schedule = build_tableau_workbook_asset_job_schedule(
    asset_def=workbook,
    cron_schedule="0 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

tableau_workbook_refresh_schedules = [
    build_tableau_workbook_refresh_schedule(asset=asset)
    for asset in external_assets
    if asset.metadata_by_key[asset.key].get("cron_schedule") is not None
]

schedules = [
    tableau_workbook_asset_job_schedule,
    *tableau_workbook_refresh_schedules,
]
