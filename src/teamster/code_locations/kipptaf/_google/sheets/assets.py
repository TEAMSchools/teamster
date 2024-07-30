from dagster import external_assets_from_specs

from teamster.code_locations.kipptaf._dbt.assets import manifest
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
    and "retired" not in source["tags"]
]

google_sheets_assets = external_assets_from_specs(specs=specs)

assets = [
    *google_sheets_assets,
]
