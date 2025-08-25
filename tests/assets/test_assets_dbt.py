from dagster import AssetsDefinition, materialize
from dagster_dbt import DbtProject


def _test_dbt_assets(
    assets: list[AssetsDefinition], code_location: str, selection: list[str]
):
    from teamster.core.resources import get_dbt_cli_resource

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


def test_dbt_assets_kippnewark():
    from teamster.code_locations.kippnewark._dbt.assets import dbt_assets

    _test_dbt_assets(
        assets=[dbt_assets],
        code_location="kippnewark",
        selection=[
            "kippnewark/powerschool/stg_powerschool__districtteachercategory",
            "kippnewark/powerschool/stg_powerschool__schoolstaff",
        ],
    )


def test_dbt_assets_kipptaf():
    from teamster.code_locations.kipptaf._dbt.assets import dbt_assets

    _test_dbt_assets(
        assets=[dbt_assets],
        code_location="kipptaf",
        selection=[
            "kipptaf/edplan/qa_edplan__powerschool_mismatch",
            "kipptaf/kippadb/qa_kippadb__hs_enrollment_audit",
            "kipptaf/people/snapshot_people__student_logins",
            "kipptaf/people/stg_people__student_logins",
            "kipptaf/powerschool/stg_powerschool__students",
        ],
    )
