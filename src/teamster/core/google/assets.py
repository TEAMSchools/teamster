from dagster import OpExecutionContext, asset

from teamster.core.google.resources.sheets import GoogleSheetsResource


def build_gsheet_asset(name, code_location, sheet_id):
    @asset(
        name=name,
        key_prefix=[code_location, "gsheets"],
        metadata={"sheet_id": sheet_id},
    )
    def _asset(context: OpExecutionContext, gsheets: GoogleSheetsResource):
        latest_materialization_event = (
            context.instance.get_latest_materialization_event(context.assets_def.key)
        )
        context.log.debug(latest_materialization_event)

        spreadsheet = gsheets.open(sheet_id=sheet_id)
        context.log.debug(spreadsheet.lastUpdateTime)

    return _asset
