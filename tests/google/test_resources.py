from dagster import build_resources

from teamster.core.google.resources.sheets import GoogleSheetsResource


def test_gsheet_resource():
    with build_resources(resources={"gsheets": GoogleSheetsResource()}) as resources:
        gsheets: GoogleSheetsResource = resources.gsheets

        print(gsheets._client.auth)
        print(vars(gsheets._client.auth))

        spreadsheet = gsheets.open(
            sheet_id="1xSa3dznVaGeqjo3Y0tS9GzkhVrpeCQ0aaKWlgI3kHik"
        )
        print(spreadsheet.lastUpdateTime)
