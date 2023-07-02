import json
import pathlib

from dagster_fivetran import build_fivetran_assets

from .. import CODE_LOCATION

schema_path = pathlib.Path(__file__).parent / "schema"

assets = []
for schema_file in schema_path.glob("*.json"):
    with schema_file.open(mode="r") as fp:
        build_fivetran_assets_kwargs = json.load(fp=fp)

    assets.extend(
        build_fivetran_assets(
            asset_key_prefix=[CODE_LOCATION], **build_fivetran_assets_kwargs
        )
    )

__all__ = [
    *assets,
]
