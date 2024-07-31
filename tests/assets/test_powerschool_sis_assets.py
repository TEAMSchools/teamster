import random

from dagster import _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.libraries.core.resources import (
    get_db_powerschool_resource,
    get_io_manager_gcs_file,
    get_ssh_powerschool_resource,
)


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
