from datetime import datetime

from dagster import DataVersion, observable_source_asset


def build_gsheet_asset(name, code_location, sheet_id, range_name):
    @observable_source_asset(
        name=name,
        key_prefix=[code_location, "gsheets"],
        metadata={"sheet_id": sheet_id, "range_name": range_name},
    )
    def _asset():
        return DataVersion(str(datetime.now().timestamp()))

    return _asset
