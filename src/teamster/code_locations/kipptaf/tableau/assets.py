import pathlib

from dagster import AssetSpec, config_from_files, external_assets_from_specs
from slugify import slugify

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.tableau.schema import WORKBOOK_SCHEMA
from teamster.libraries.tableau.assets import build_tableau_workbook_stats_asset

config_assets = config_from_files(
    [f"{pathlib.Path(__file__).parent}/config/assets.yaml"]
)["assets"]

workbook_stats = build_tableau_workbook_stats_asset(
    code_location=CODE_LOCATION,
    workbook_ids=[a["metadata"]["id"] for a in config_assets],
    partition_start_date="2024-02-26",
    schema=WORKBOOK_SCHEMA,
)

specs = [
    AssetSpec(
        key=[
            CODE_LOCATION,
            "tableau",
            slugify(text=a["name"], separator="_", regex_pattern=r"[^A-Za-z0-9_]"),
        ],
        description=a["name"],
        deps=a["deps"],
        metadata=a["metadata"],
        group_name="tableau",
    )
    for a in config_assets
]

workbook_refresh_assets = external_assets_from_specs(specs)

assets = [
    workbook_stats,
    *workbook_refresh_assets,
]
