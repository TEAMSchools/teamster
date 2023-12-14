import re

from dagster import AssetSpec, external_asset_from_spec

from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.dbt.manifest import dbt_manifest


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


google_sheets_assets = [
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

_all = [
    google_sheets_assets,
]
