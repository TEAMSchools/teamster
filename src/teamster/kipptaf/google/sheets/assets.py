from teamster.core.google.sheets.assets import build_gsheet_asset

from ... import CODE_LOCATION
from ...dbt.assets import dbt_manifest

google_sheets_assets = [
    build_gsheet_asset(
        code_location=CODE_LOCATION,
        name=source["name"].split("__")[-1],
        source_name=source["source_name"],
        uri=source["external"]["options"]["uris"][0],
        range_name=source["external"]["options"]["sheet_range"],
    )
    for source in dbt_manifest["sources"].values()
    if source.get("external")
    and source["external"]["options"]["format"] == "GOOGLE_SHEETS"
]
