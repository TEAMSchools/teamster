from dagster import build_resources
from gspread import Spreadsheet

from teamster.core.google.resources.sheets import GoogleSheetsResource


def test_gsheet_resource():
    with build_resources(resources={"gsheets": GoogleSheetsResource()}) as resources:
        spreadsheet: Spreadsheet = resources.gsheets.open(
            sheet_id="1xSa3dznVaGeqjo3Y0tS9GzkhVrpeCQ0aaKWlgI3kHik"
        )

        print(spreadsheet)
        print(spreadsheet.lastUpdateTime)
