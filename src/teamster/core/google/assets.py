import pendulum
from dagster import DataVersion, observable_source_asset

from teamster.core.google.resources.sheets import GoogleSheetsResource


def build_gsheet_asset(name, code_location, sheet_id):
    @observable_source_asset(
        name=name,
        key_prefix=[code_location, "gsheets"],
        metadata={"sheet_id": sheet_id},
    )
    def _asset(gsheets: GoogleSheetsResource):
        spreadsheet = gsheets.open(sheet_id=sheet_id)

        last_update_timestamp = pendulum.parser.parse(
            text=spreadsheet.lastUpdateTime
        ).timestamp()

        return DataVersion(last_update_timestamp)

    return _asset
