from dagster import build_resources

from teamster.core.google.resources.sheets import GoogleSheetsResource


def test_gsheet_resource():
    with build_resources(
        resources={
            "gsheets": GoogleSheetsResource(
                service_account_file_path="env/gcloud-service-account.json"
            )
        }
    ) as resources:
        gsheets: GoogleSheetsResource = resources.gsheets

        print(gsheets._client.auth.service_account_email)

        spreadsheet = gsheets.open(
            sheet_id="1xSa3dznVaGeqjo3Y0tS9GzkhVrpeCQ0aaKWlgI3kHik"
        )

        print(spreadsheet.lastUpdateTime)
