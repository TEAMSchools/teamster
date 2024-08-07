import pathlib

from dagster import config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.schema import WORKBOOK_SCHEMA
from teamster.libraries.tableau.assets import (
    build_tableau_workbook_refresh_asset,
    build_tableau_workbook_stats_asset,
)

config_assets = config_from_files(
    [f"{pathlib.Path(__file__).parent}/config/assets.yaml"]
)["assets"]

workbook_stats = build_tableau_workbook_stats_asset(
    code_location=CODE_LOCATION,
    workbook_ids=[a["metadata"]["id"] for a in config_assets],
    partition_start_date="2024-02-26",
    schema=WORKBOOK_SCHEMA,
)

workbook_refresh_assets = [
    build_tableau_workbook_refresh_asset(
        code_location=CODE_LOCATION,
        timezone=LOCAL_TIMEZONE.name,
        cron_schedule=a["metadata"]["cron_schedule"],
        **a,
    )
    for a in config_assets
]

assets = [
    workbook_stats,
    *workbook_refresh_assets,
]
