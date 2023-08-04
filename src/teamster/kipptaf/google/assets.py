from dagster import StaticPartitionsDefinition

from teamster.core.google.directory.assets import (
    build_google_directory_assets,
    build_google_directory_partitioned_assets,
)
from teamster.core.google.forms.assets import build_google_forms_assets
from teamster.core.google.sheets.assets import build_gsheet_asset
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.dbt.assets import DBT_MANIFEST

# google sheets
google_sheets_assets = [
    build_gsheet_asset(
        code_location=CODE_LOCATION,
        name=source["name"][4:],
        uri=source["external"]["options"]["uris"][0],
        range_name=source["external"]["options"]["sheet_range"],
    )
    for source in DBT_MANIFEST["sources"].values()
    if source.get("external")
    and source["external"]["options"]["format"] == "GOOGLE_SHEETS"
]

# google forms
FORM_IDS = [
    "1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA",
]

google_forms_assets = build_google_forms_assets(
    code_location=CODE_LOCATION,
    partitions_def=StaticPartitionsDefinition(FORM_IDS),
)

# google admin
google_directory_assets = build_google_directory_assets(code_location=CODE_LOCATION)
google_directory_partitioned_assets = build_google_directory_partitioned_assets(
    code_location=CODE_LOCATION,
    partitions_def=StaticPartitionsDefinition(
        # group keys
        [
            "group-students-camden@teamstudents.org",
            "group-students-miami@teamstudents.org",
            "group-students-newark@teamstudents.org",
        ]
    ),
)

google_directory_assets = [
    *google_directory_assets,
    *google_directory_partitioned_assets,
]

__all__ = [
    *google_sheets_assets,
    *google_forms_assets,
    *google_directory_assets,
]
