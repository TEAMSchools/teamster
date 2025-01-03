import pathlib

from dagster import config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.libraries.sftp.assets import build_sftp_folder_asset
from teamster.libraries.tableau.assets import build_tableau_workbook_refresh_asset

config_assets = config_from_files(
    [f"{pathlib.Path(__file__).parent}/config/assets.yaml"]
)["assets"]

workbook_refresh_assets = [
    build_tableau_workbook_refresh_asset(
        code_location=CODE_LOCATION,
        cron_timezone=str(LOCAL_TIMEZONE),
        cron_schedule=a["metadata"].get("cron_schedule"),
        **a,
    )
    for a in config_assets
]

traffic_to_views = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "tableau", "traffic_to_views"],
    remote_dir_regex=r"/data-team/kipptaf/tableau/traffic_to_views",
    remote_file_regex=r"tableau_usage_\d+\.csv",
    avro_schema=...,
    ssh_resource_key="ssh_couchdrop",
)

assets = [
    *workbook_refresh_assets,
]
