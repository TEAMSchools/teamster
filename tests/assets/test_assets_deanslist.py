import random

from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.core.resources import (
    DEANSLIST_RESOURCE,
    get_io_manager_gcs_avro,
    get_io_manager_gcs_file,
)


def _test_asset(assets, asset_name, partition_key: str | None = None):
    asset = [a for a in assets if a.key.path[-1] == asset_name][0]

    if partition_key is None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "io_manager_gcs_file": get_io_manager_gcs_file(
                code_location="test", test=True
            ),
            "deanslist": DEANSLIST_RESOURCE,
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

    asset_check_evaluations = result.get_asset_check_evaluations()

    if asset_check_evaluations:
        extras = _check.inst(
            obj=asset_check_evaluations[0].metadata.get("extras"),
            ttype=TextMetadataValue,
        )

        assert extras.text == ""


def test_asset_deanslist_lists_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="lists")


def test_asset_deanslist_terms_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="terms")


def test_asset_deanslist_roster_assignments_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="roster_assignments")


def test_asset_deanslist_users_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="users")


def test_asset_deanslist_rosters_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="rosters")


def test_asset_deanslist_students_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="students")


def test_asset_deanslist_homework_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        monthly_multi_partitions_assets,
    )

    _test_asset(assets=monthly_multi_partitions_assets, asset_name="homework")


def test_asset_deanslist_comm_log_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(
        assets=fiscal_multi_partitions_assets,
        asset_name="comm_log",
        partition_key="2024-07-01|522",
    )


def test_asset_deanslist_followups_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(assets=fiscal_multi_partitions_assets, asset_name="followups")


def test_asset_deanslist_lists_kippcamden():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="lists")


def test_asset_deanslist_terms_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="terms")


def test_asset_deanslist_roster_assignments_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="roster_assignments")


def test_asset_deanslist_users_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="users")


def test_asset_deanslist_rosters_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="rosters")


def test_asset_deanslist_students_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="students")


def test_asset_deanslist_homework_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        monthly_multi_partitions_assets,
    )

    _test_asset(assets=monthly_multi_partitions_assets, asset_name="homework")


def test_asset_deanslist_comm_log_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(assets=fiscal_multi_partitions_assets, asset_name="comm_log")


def test_asset_deanslist_followups_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(assets=fiscal_multi_partitions_assets, asset_name="followups")


def test_asset_deanslist_lists_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="lists")


def test_asset_deanslist_terms_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="terms")


def test_asset_deanslist_roster_assignments_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="roster_assignments")


def test_asset_deanslist_users_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="users")


def test_asset_deanslist_rosters_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="rosters")


def test_asset_deanslist_students_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="students")


def test_asset_deanslist_homework_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        monthly_multi_partitions_assets,
    )

    _test_asset(assets=monthly_multi_partitions_assets, asset_name="homework")


def test_asset_deanslist_comm_log_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(assets=fiscal_multi_partitions_assets, asset_name="comm_log")


def test_asset_deanslist_followups_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(assets=fiscal_multi_partitions_assets, asset_name="followups")


def test_asset_deanslist_dff_stats_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="dff_stats")


def test_asset_deanslist_dff_stats_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="dff_stats")


def test_asset_deanslist_dff_stats_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        static_partitions_assets,
    )

    _test_asset(assets=static_partitions_assets, asset_name="dff_stats")


def test_asset_deanslist_behavior_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(
        assets=fiscal_multi_partitions_assets,
        asset_name="behavior",
        partition_key="2024-07-01|472",
    )


def test_asset_deanslist_behavior_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(
        assets=fiscal_multi_partitions_assets,
        asset_name="behavior",
        partition_key="2024-07-01|120",
    )


def test_asset_deanslist_behavior_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        fiscal_multi_partitions_assets,
    )

    _test_asset(
        assets=fiscal_multi_partitions_assets,
        asset_name="behavior",
        partition_key="2024-07-01|124",
    )


def test_asset_deanslist_incidents_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.assets import (
        monthly_multi_partitions_assets,
    )

    _test_asset(
        assets=monthly_multi_partitions_assets,
        asset_name="incidents",
        partition_key="2024-11-01|473",
    )


def test_asset_deanslist_incidents_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.assets import (
        monthly_multi_partitions_assets,
    )

    _test_asset(
        assets=monthly_multi_partitions_assets,
        asset_name="incidents",
        partition_key="2024-11-01|472",
    )


def test_asset_deanslist_incidents_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.assets import (
        monthly_multi_partitions_assets,
    )

    _test_asset(
        assets=monthly_multi_partitions_assets,
        asset_name="incidents",
        partition_key="2024-11-01|124",
    )
