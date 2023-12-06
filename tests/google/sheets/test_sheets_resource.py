import pendulum
from dagster import build_resources, config_from_files

from teamster.kipptaf.google.sheets.assets import build_gsheet_asset
from teamster.kipptaf.google.sheets.resources import GoogleSheetsResource

CODE_LOCATION = "kipptaf"


def test_gsheet_resource():
    config_dir = f"src/teamster/{CODE_LOCATION}/google/config"

    asset_defs = [
        build_gsheet_asset(code_location=CODE_LOCATION, **asset)
        for asset in config_from_files([f"{config_dir}/assets.yaml"])["assets"]
    ]

    with build_resources(
        resources={
            "gsheets": GoogleSheetsResource(
                service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
            )
        }
    ) as resources:
        gsheets: GoogleSheetsResource = resources.gsheets

    for asset in asset_defs:
        sheet_id = asset.metadata["sheet_id"].value

        print(sheet_id)
        spreadsheet = gsheets.open(sheet_id=sheet_id)

        last_update_timestamp = pendulum.parser.parse(
            text=spreadsheet.lastUpdateTime
        ).timestamp()

        print(f"\t{last_update_timestamp}")
