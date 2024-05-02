import re

from dagster import AssetSpec

from teamster.core.definitions.external_asset import external_assets_from_specs
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.dbt.assets import manifest


def build_google_sheets_asset_spec(source_name, name, uri, range_name):
    re_match = re.match(
        pattern=r"https:\/{2}docs\.google\.com\/spreadsheets\/d\/([\w-]+)", string=uri
    )

    return AssetSpec(
        key=[CODE_LOCATION, source_name, name],
        metadata={"sheet_id": re_match.group(1), "range_name": range_name},
        group_name="google_sheets",
    )


specs = [
    build_google_sheets_asset_spec(
        source_name=source["source_name"],
        name=source["name"].split("__")[-1],
        uri=source["external"]["options"]["uris"][0],
        range_name=source["external"]["options"]["sheet_range"],
    )
    for source in manifest["sources"].values()
    if source.get("external")
    and source["external"]["options"]["format"] == "GOOGLE_SHEETS"
]

google_sheets_assets = external_assets_from_specs(
    specs=specs, compute_kind="googlesheets"
)

assets = [
    *google_sheets_assets,
]
