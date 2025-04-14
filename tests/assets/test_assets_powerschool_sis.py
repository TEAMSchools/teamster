import random

from dagster import materialize
from dagster_shared import check


def _test_asset(assets, asset_name: str, code_location: str):
    from teamster.core.resources import (
        get_io_manager_gcs_file,
    )
    from tests.utils import get_db_powerschool_resource, get_ssh_powerschool_resource

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
            "ssh_powerschool": get_ssh_powerschool_resource(code_location),
            "db_powerschool": get_db_powerschool_resource(code_location),
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    records = check.inst(
        # trunk-ignore(pyright/reportAttributeAccessIssue,pyright/reportOptionalMemberAccess)
        asset_materialization_event.event_specific_data.materialization.metadata[
            "records"
        ].value,
        int,
    )

    assert records > 0


def test_schools_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets, asset_name="schools", code_location=CODE_LOCATION.upper()
    )


def test_reenrollments_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets, asset_name="reenrollments", code_location=CODE_LOCATION.upper()
    )


def test_cc_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(assets=assets, asset_name="cc", code_location=CODE_LOCATION.upper())


def test_u_studentsuserfields_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        code_location=CODE_LOCATION.upper(),
    )


def test_u_studentsuserfields_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        code_location=CODE_LOCATION.upper(),
    )


def test_u_studentsuserfields_kippmiami():
    from teamster.code_locations.kippmiami import CODE_LOCATION
    from teamster.code_locations.kippmiami.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_studentsuserfields",
        code_location=CODE_LOCATION.upper(),
    )


def test_log_kippmiami():
    from teamster.code_locations.kippmiami import CODE_LOCATION
    from teamster.code_locations.kippmiami.powerschool import assets

    _test_asset(assets=assets, asset_name="log", code_location=CODE_LOCATION.upper())


def test_log_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(assets=assets, asset_name="log", code_location=CODE_LOCATION.upper())


def test_log_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(assets=assets, asset_name="log", code_location=CODE_LOCATION.upper())


def test_gpnode_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(assets=assets, asset_name="gpnode", code_location=CODE_LOCATION.upper())


def test_gpprogresssubject_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubject",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpprogresssubjectwaived_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjectwaived",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpprogresssubjectearned_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjectearned",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpstudentwaiver_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets, asset_name="gpstudentwaiver", code_location=CODE_LOCATION.upper()
    )


def test_gpversion_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets, asset_name="gpversion", code_location=CODE_LOCATION.upper()
    )


def test_gradplan_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets, asset_name="gradplan", code_location=CODE_LOCATION.upper()
    )


def test_userscorefields_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets, asset_name="userscorefields", code_location=CODE_LOCATION.upper()
    )


def test_u_storedgrades_de_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_storedgrades_de",
        code_location=CODE_LOCATION.upper(),
    )


def test_u_storedgrades_de_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="u_storedgrades_de",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpnode_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(assets=assets, asset_name="gpnode", code_location=CODE_LOCATION.upper())


def test_gpprogresssubject_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubject",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpprogresssubjectearned_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjectearned",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpprogresssubjectenrolled_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjectenrolled",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpprogresssubjectrequested_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjectrequested",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpprogresssubjectwaived_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjectwaived",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpprogresssubjwaivedapplied_kippnewark():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpprogresssubjwaivedapplied",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpselectedcrs_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets, asset_name="gpselectedcrs", code_location=CODE_LOCATION.upper()
    )


def test_gpselectedcrtype_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets,
        asset_name="gpselectedcrtype",
        code_location=CODE_LOCATION.upper(),
    )


def test_gpselector_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets, asset_name="gpselector", code_location=CODE_LOCATION.upper()
    )


def test_gptarget_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets, asset_name="gptarget", code_location=CODE_LOCATION.upper()
    )


def test_gpversion_kippcamden():
    from teamster.code_locations.kippcamden import CODE_LOCATION
    from teamster.code_locations.kippcamden.powerschool import assets

    _test_asset(
        assets=assets, asset_name="gpversion", code_location=CODE_LOCATION.upper()
    )
