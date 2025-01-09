import pathlib

from dagster import config_from_files

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.tableau.schema import VIEW_COUNT_PER_VIEW
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

view_count_per_view = build_sftp_folder_asset(
    asset_key=[CODE_LOCATION, "tableau", "view_count_per_view"],
    remote_dir_regex=r"/data-team/kipptaf/tableau/view_count_per_view",
    remote_file_regex=r".+\.csv",
    file_sep="\t",
    file_encoding="utf-16",
    avro_schema=VIEW_COUNT_PER_VIEW,
    ssh_resource_key="ssh_couchdrop",
)

assets = [
    view_count_per_view,
    *workbook_refresh_assets,
]
