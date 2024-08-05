from teamster.code_locations.kipptaf import LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.assets import (
    workbook_refresh_assets,
    workbook_stats,
)
from teamster.libraries.tableau.schedules import (
    build_tableau_workbook_refresh_schedule,
    build_tableau_workbook_stats_schedule,
)

tableau_workbook_stats_asset_job_schedule = build_tableau_workbook_stats_schedule(
    asset_def=workbook_stats,
    cron_schedule="0 1 * * *",
    execution_timezone=LOCAL_TIMEZONE.name,
)

tableau_workbook_refresh_schedules = [
    build_tableau_workbook_refresh_schedule(
        asset=asset, execution_timezone=LOCAL_TIMEZONE.name
    )
    for asset in workbook_refresh_assets
    if asset.metadata_by_key[asset.key].get("cron_schedule") is not None
]

schedules = [
    tableau_workbook_stats_asset_job_schedule,
    *tableau_workbook_refresh_schedules,
]
