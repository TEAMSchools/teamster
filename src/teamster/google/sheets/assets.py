import re

from dagster import AssetSpec


def build_google_sheets_asset_spec(code_location, source_name, name, uri, range_name):
    re_match = re.match(
        pattern=r"https:\/{2}docs\.google\.com\/spreadsheets\/d\/([\w-]+)", string=uri
    )

    return AssetSpec(
        key=[code_location, source_name, name],
        metadata={"sheet_id": re_match.group(1), "range_name": range_name},
        group_name="google_sheets",
    )
