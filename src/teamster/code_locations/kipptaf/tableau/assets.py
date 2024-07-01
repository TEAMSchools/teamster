import pathlib

from dagster import AssetKey, AssetsDefinition, AssetSpec, config_from_files
from slugify import slugify

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.tableau.schema import WORKBOOK_SCHEMA
from teamster.libraries.core.definitions.external_asset import (
    external_assets_from_specs,
)
from teamster.libraries.tableau.assets import build_tableau_workbook_asset

config = config_from_files([f"{pathlib.Path(__file__).parent}/config/assets.yaml"])

workbook = build_tableau_workbook_asset(
    code_location=CODE_LOCATION,
    workbook_ids=[a["metadata"]["id"] for a in config["external_assets"]],
    partition_start_date="2024-02-26",
    schema=WORKBOOK_SCHEMA,
)

specs = [
    AssetSpec(
        key=AssetKey(
            [
                CODE_LOCATION,
                "tableau",
                slugify(text=a["name"], separator="_", regex_pattern=r"[^A-Za-z0-9_]"),
            ]
        ),
        description=a["name"],
        deps=a["deps"],
        metadata=a["metadata"],
        group_name="tableau",
    )
    for a in config["external_assets"]
]

external_assets: list[AssetsDefinition] = external_assets_from_specs(
    specs=specs, compute_kind="tableau"
)

assets = [
    workbook,
    *external_assets,
]
