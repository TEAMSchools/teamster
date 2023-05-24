from dagster import OpExecutionContext, asset

from teamster.core.google.resources.sheets import GoogleSheetsResource


def build_gsheet_asset(name, code_location, sheet_id):
    @asset(
        name=name,
        key_prefix=[code_location, "gsheets"],
        metadata={"sheet_id": sheet_id},
    )
    def _asset(context: OpExecutionContext, gsheets: GoogleSheetsResource):
        spreadsheet = gsheets.open(sheet_id=sheet_id)
        context.log.debug(spreadsheet._properties)

        named_ranges = spreadsheet.list_named_ranges()
        context.log.debug(named_ranges)

        named_range_match = [
            nr for nr in spreadsheet.list_named_ranges() if nr["name"] == name
        ]

        if named_range_match:
            worksheet = spreadsheet.get_worksheet_by_id(
                id=named_range_match[0]["range"].get("sheetId", 0)
            )
        else:
            worksheet = spreadsheet.sheet1

        context.log.debug(worksheet._properties)

    return _asset
