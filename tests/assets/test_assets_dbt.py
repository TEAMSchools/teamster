from dagster import AssetsDefinition, materialize
from dagster_dbt import DbtProject

from teamster.core.resources import get_dbt_cli_resource


def _test_dbt_assets(
    assets: list[AssetsDefinition], code_location: str, selection: list[str]
):
    result = materialize(
        assets=assets,
        resources={
            "dbt_cli": get_dbt_cli_resource(
                dbt_project=DbtProject(project_dir=f"src/dbt/{code_location}"),
                test=True,
            )
        },
        selection=selection,
    )

    assert result.success


def test_dbt_assets_kipptaf():
    from teamster.code_locations.kipptaf._dbt.assets import dbt_assets

    _test_dbt_assets(
        assets=[dbt_assets],
        code_location="kipptaf",
        selection=[
            "kipptaf/schoolmint_grow/stg_schoolmint_grow__users",
            "kipptaf/schoolmint_grow/stg_schoolmint_grow__schools",
            "kipptaf/schoolmint_grow/int_schoolmint_grow__observations",
            "kipptaf/illuminate/stg_illuminate__reporting_groups",
        ],
    )
