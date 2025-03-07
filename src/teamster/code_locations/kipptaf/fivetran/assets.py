import pathlib

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.fivetran.assets import build_fivetran_asset_specs

config_dir = pathlib.Path(__file__).parent / "config"

illuminate_xmin_assets = build_fivetran_asset_specs(
    config_file=config_dir / "illuminate_xmin.yaml",
    code_location=CODE_LOCATION,
    kinds=["postgresql"],
)

illuminate_assets = build_fivetran_asset_specs(
    config_file=config_dir / "illuminate.yaml",
    code_location=CODE_LOCATION,
    kinds=["postgresql"],
)

asset_specs = [
    *illuminate_xmin_assets,
    *illuminate_assets,
]
