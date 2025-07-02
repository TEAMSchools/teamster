from dagster import Definitions, load_assets_from_modules

from teamster.code_locations.kipptaf import DBT_PROJECT, _dbt
from teamster.core.resources import get_dbt_cli_resource

defs = Definitions(
    assets=[*load_assets_from_modules(modules=[_dbt])],
    resources={"dbt_cli": get_dbt_cli_resource(DBT_PROJECT)},
)
