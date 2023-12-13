import re

from dagster import AssetSpec, external_asset_from_spec

from ... import CODE_LOCATION
from ...dbt.assets import dbt_manifest


def build_google_sheets_asset(source_name, name, uri, range_name):
    re_match = re.match(
        pattern=r"https:\/{2}docs\.google\.com\/spreadsheets\/d\/([\w-]+)", string=uri
    )

    return external_asset_from_spec(
        AssetSpec(
            key=[CODE_LOCATION, source_name, name],
            metadata={"sheet_id": re_match.group(1), "range_name": range_name},
            group_name="google_sheets",
        )
    )


_all = [
    build_google_sheets_asset(
        source_name=source["source_name"],
        name=source["name"].split("__")[-1],
        uri=source["external"]["options"]["uris"][0],
        range_name=source["external"]["options"]["sheet_range"],
    )
    for source in dbt_manifest["sources"].values()
    if source.get("external")
    and source["external"]["options"]["format"] == "GOOGLE_SHEETS"
]
