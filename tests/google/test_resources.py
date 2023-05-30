import pendulum
from dagster import build_resources

from teamster.core.google.resources.sheets import GoogleSheetsResource


def test_gsheet_resource():
    with build_resources(
        resources={
            "gsheets": GoogleSheetsResource(
                service_account_file_path="env/gcloud_service_account_json"
            )
        }
    ) as resources:
        gsheets: GoogleSheetsResource = resources.gsheets

        print(vars(gsheets._client.auth))

        spreadsheet = gsheets.open(
            sheet_id="1xSa3dznVaGeqjo3Y0tS9GzkhVrpeCQ0aaKWlgI3kHik"
        )

        print(vars(spreadsheet.client.auth))

        last_update_timestamp = pendulum.parser.parse(
            text=spreadsheet.lastUpdateTime
        ).timestamp()

        print(last_update_timestamp)
