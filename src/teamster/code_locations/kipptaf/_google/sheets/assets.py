from teamster.code_locations.kipptaf._dbt.assets import manifest
from teamster.libraries.google.sheets.assets import build_google_sheets_asset_spec

asset_specs = [
    build_google_sheets_asset_spec(
        asset_key=source["meta"]["dagster"]["asset_key"],
        uri=source["external"]["options"]["uris"][0],
        range_name=source["external"]["options"]["sheet_range"],
    )
    for source in manifest["sources"].values()
    if source.get("external")
    and source["external"]["options"]["format"] == "GOOGLE_SHEETS"
]
