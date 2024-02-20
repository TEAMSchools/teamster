from dagster import Definitions, load_assets_from_modules

from teamster.core.resources import get_dbt_cli_resource

from . import CODE_LOCATION, assets
from .dbt import assets as dbt_assets

defs = Definitions(
    assets=load_assets_from_modules(
        modules=[
            assets,
            dbt_assets,
        ]
    ),
    resources={
        "dbt_cli": get_dbt_cli_resource(CODE_LOCATION),
    },
)
