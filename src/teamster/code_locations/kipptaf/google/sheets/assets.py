from teamster.code_locations.kipptaf.dbt.assets import manifest
from teamster.libraries.core.definitions.external_asset import (
    external_assets_from_specs,
)
from teamster.libraries.google.sheets.assets import build_google_sheets_asset_spec

specs = [
    build_google_sheets_asset_spec(
        asset_key=source["meta"]["dagster"]["parent_asset_key_path"],
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
