import random

from dagster import AssetsDefinition, materialize
from dagster._core.definitions.asset_selection import CoercibleToAssetSelection


def _test_assets(
    assets: list[AssetsDefinition],
    selection: CoercibleToAssetSelection,
    code_location: str,
    partition_key: str | None = None,
):
    from teamster.core.resources import (
        get_io_manager_gcs_file,
    )
    from tests.utils import get_db_powerschool_resource, get_ssh_powerschool_resource

    result = materialize(
        assets=assets,
        selection=selection,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_file": get_io_manager_gcs_file("test"),
            "ssh_powerschool": get_ssh_powerschool_resource(code_location),
            "db_powerschool": get_db_powerschool_resource(code_location),
        },
    )

    assert result.success

    for event in result.get_asset_materialization_events():
        records = event.step_materialization_data.materialization.metadata["records"]

        assert isinstance(records.value, int)
        # assert records.value > 0


def _test_partitioned_asset(
    assets: list[AssetsDefinition], asset_name: str, code_location: str
):
    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

    if asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    _test_assets(
        assets=[asset],
        selection=[asset.key],
        code_location=code_location,
        partition_key=partition_key,
    )


def test_schools_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="schools", code_location=CODE_LOCATION.upper()
    )


def test_reenrollments_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="reenrollments", code_location=CODE_LOCATION.upper()
    )


def test_cc_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="cc", code_location=CODE_LOCATION.upper()
    )


def test_u_studentsuserfields_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        code_location=CODE_LOCATION.upper(),
    )


def test_u_studentsuserfields_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_partitioned_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        code_location=CODE_LOCATION.upper(),
    )


def test_u_studentsuserfields_kippmiami():
    from teamster.code_locations.kippmiami import CODE_LOCATION
    from teamster.code_locations.kippmiami.powerschool import assets

    _test_partitioned_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        code_location=CODE_LOCATION.upper(),
    )


def test_log_kippmiami():
    from teamster.code_locations.kippmiami import CODE_LOCATION
    from teamster.code_locations.kippmiami.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="log", code_location=CODE_LOCATION.upper()
    )


def test_log_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="log", code_location=CODE_LOCATION.upper()
    )


def test_log_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="log", code_location=CODE_LOCATION.upper()
    )


def test_gradplan_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="gradplan", code_location=CODE_LOCATION.upper()
    )


def test_userscorefields_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets, asset_name="userscorefields", code_location=CODE_LOCATION.upper()
    )


def test_u_storedgrades_de_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_partitioned_asset(
        assets=assets,
        asset_name="u_storedgrades_de",
        code_location=CODE_LOCATION.upper(),
    )


def test_u_storedgrades_de_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_partitioned_asset(
        assets=assets,
        asset_name="u_storedgrades_de",
        code_location=CODE_LOCATION.upper(),
    )


def test_grad_plan_assets_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_assets(
        assets=assets,
        code_location=CODE_LOCATION.upper(),
        selection=[
            f"{CODE_LOCATION}/powerschool/gpnode",
            f"{CODE_LOCATION}/powerschool/gpprogresssubject",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectearned",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectenrolled",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectrequested",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectwaived",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjwaivedapplied",
            f"{CODE_LOCATION}/powerschool/gpselectedcrs",
            f"{CODE_LOCATION}/powerschool/gpselectedcrtype",
            f"{CODE_LOCATION}/powerschool/gpselector",
            f"{CODE_LOCATION}/powerschool/gpstudentwaiver",
            f"{CODE_LOCATION}/powerschool/gptarget",
            f"{CODE_LOCATION}/powerschool/gpversion",
        ],
    )


def test_grad_plan_assets_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_assets(
        assets=assets,
        code_location=CODE_LOCATION.upper(),
        selection=[
            f"{CODE_LOCATION}/powerschool/gpnode",
            f"{CODE_LOCATION}/powerschool/gpprogresssubject",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectearned",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectenrolled",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectrequested",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjectwaived",
            f"{CODE_LOCATION}/powerschool/gpprogresssubjwaivedapplied",
            f"{CODE_LOCATION}/powerschool/gpselectedcrs",
            f"{CODE_LOCATION}/powerschool/gpselectedcrtype",
            f"{CODE_LOCATION}/powerschool/gpselector",
            f"{CODE_LOCATION}/powerschool/gpstudentwaiver",
            f"{CODE_LOCATION}/powerschool/gptarget",
            f"{CODE_LOCATION}/powerschool/gpversion",
        ],
    )


def test_powerschool_s_stu_x_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_assets(
        assets=assets,
        code_location=CODE_LOCATION.upper(),
        selection=[f"{CODE_LOCATION}/powerschool/s_stu_x"],
    )
