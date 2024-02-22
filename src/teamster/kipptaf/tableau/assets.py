import pathlib

from dagster import AssetKey, AssetsDefinition, AssetSpec, config_from_files
from slugify import slugify

from teamster.core.definitions.external_asset import external_assets_from_specs

from .. import CODE_LOCATION

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
    for a in config_from_files([f"{pathlib.Path(__file__).parent}/config/assets.yaml"])[
        "assets"
    ]
]

_all: list[AssetsDefinition] = external_assets_from_specs(
    specs=specs, compute_kind="tableau"
)
