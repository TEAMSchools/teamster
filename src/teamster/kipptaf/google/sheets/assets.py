from teamster.core.definitions.external_asset import external_assets_from_specs
from teamster.google.sheets.assets import build_google_sheets_asset_spec
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.dbt.assets import manifest

specs = [
    build_google_sheets_asset_spec(
        asset_key=[
            CODE_LOCATION,
            source["source_name"],
            source["name"].split("__")[-1],
        ],
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
