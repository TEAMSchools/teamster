import re

from dagster import AssetSpec
from dagster_shared import check


def build_google_sheets_asset_spec(asset_key, uri, range_name):
    match = check.not_none(
        value=re.match(
            pattern=r"https:/{2}docs\.google\.com/spreadsheets/d/([\w-]+)",
            string=uri,
        )
    )

    return AssetSpec(
        key=asset_key,
        metadata={"sheet_id": match.group(1), "range_name": range_name},
        group_name="google_sheets",
        kinds={"googlesheets"},
    )
