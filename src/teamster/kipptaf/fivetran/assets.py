import json
import os
import pathlib

# from dagster import with_resources
from dagster_fivetran import build_fivetran_assets

schema_path = pathlib.Path(__file__).parent / "schema"
# fivetran_instance = FivetranResource(
#     api_key=os.getenv("FIVETRAN_API_KEY"), api_secret=os.getenv("FIVETRAN_API_SECRET")
# )

assets = []
for schema_file in schema_path.glob("*.json"):
    with schema_file.open(mode="r") as fp:
        build_fivetran_assets_kwargs = json.load(fp=fp)

    assets.extend(
        build_fivetran_assets(**build_fivetran_assets_kwargs)
        # with_resources(
        #     definitions=build_fivetran_assets(**build_fivetran_assets_kwargs),
        #     resource_defs={"fivetran": fivetran_instance},
        # )
    )

__all__ = [
    *assets,
]
