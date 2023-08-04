import re
from datetime import datetime

from dagster import DataVersion, observable_source_asset


def build_gsheet_asset(code_location, source_name, name, uri, range_name):
    re_match = re.match(
        pattern=r"https:\/{2}docs\.google\.com\/spreadsheets\/d\/([\w-]+)", string=uri
    )

    @observable_source_asset(
        name=name,
        key_prefix=[code_location, source_name],
        metadata={"sheet_id": re_match.group(1), "range_name": range_name},
    )
    def _asset():
        return DataVersion(str(datetime.now().timestamp()))

    return _asset
