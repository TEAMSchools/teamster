import random

from dagster import _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.core.resources import (
    get_io_manager_gcs_file,
)
from tests.utils import get_db_powerschool_resource, get_ssh_powerschool_resource


def _test_asset(assets, asset_name, ssh_powerschool, db_powerschool):
    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

    if asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_file": get_io_manager_gcs_file("test"),
            "ssh_powerschool": ssh_powerschool,
            "db_powerschool": db_powerschool,
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )

    assert records > 0


def test_schools_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="schools",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_reenrollments_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="reenrollments",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_cc_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="cc",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_u_studentsuserfields_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_u_studentsuserfields_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_u_studentsuserfields_kippmiami():
    from teamster.code_locations.kippmiami import CODE_LOCATION
    from teamster.code_locations.kippmiami.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_log_kippmiami():
    from teamster.code_locations.kippmiami import CODE_LOCATION
    from teamster.code_locations.kippmiami.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="log",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_log_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="log",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_log_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="log",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_gpnode_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpnode",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_gpprogresssubject_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubject",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_gpprogresssubjectwaived_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjectwaived",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_gpstudentwaiver_kippnewark():  # whenmodified
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpstudentwaiver",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_gpversion_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpversion",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_gradplan_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gradplan",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )


def test_userscorefields_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="userscorefields",
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )
