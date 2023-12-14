from ...dbt.assets import dbt_manifest
from .assets import build_google_sheets_asset
from .sensors import build_google_sheets_asset_sensor

assets = [
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

sensors = build_google_sheets_asset_sensor(assets)

_all = [
    assets,
    sensors,
]
