import random

from dagster import (
    DynamicPartitionsDefinition,
    EnvVar,
    MultiPartitionsDefinition,
    _check,
    instance_for_test,
    materialize,
)
from dagster._core.events import StepMaterializationData

from teamster.libraries.core.resources import (
    SSH_COUCHDROP,
    SSH_IREADY,
    get_io_manager_gcs_avro,
)
from teamster.libraries.ssh.resources import SSHResource


def _test_asset(asset, ssh_resource: dict, partition_key=None, instance=None):
    if partition_key is not None:
        pass
    elif asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys(
            dynamic_partitions_store=instance
        )

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            **ssh_resource,
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]
    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    step_materialization_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        step_materialization_data.materialization.metadata["records"].value, int
    )

    assert records > 0

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_edplan_kippcamden():
    from teamster.code_locations.kippcamden.edplan.assets import njsmart_powerschool

    _test_asset(
        asset=njsmart_powerschool,
        ssh_resource={
            "ssh_edplan": SSHResource(
                remote_host="secureftp.easyiep.com",
                username=EnvVar("EDPLAN_SFTP_USERNAME_KIPPCAMDEN"),
                password=EnvVar("EDPLAN_SFTP_PASSWORD_KIPPCAMDEN"),
            )
        },
    )


def test_edplan_kippnewark():
    from teamster.code_locations.kippnewark.edplan.assets import njsmart_powerschool

    _test_asset(
        asset=njsmart_powerschool,
        ssh_resource={
            "ssh_edplan": SSHResource(
                remote_host="secureftp.easyiep.com",
                username=EnvVar("EDPLAN_SFTP_USERNAME_KIPPNEWARK"),
                password=EnvVar("EDPLAN_SFTP_PASSWORD_KIPPNEWARK"),
            )
        },
    )


def test_iready_diagnostic_results_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "diagnostic_results"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_iready_diagnostic_results_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "diagnostic_results"][0]

    _test_asset(
        asset=asset, ssh_resource={"ssh_iready": SSH_IREADY}, partition_key="2021|math"
    )


def test_iready_personalized_instruction_by_lesson_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import assets

    asset = [
        a for a in assets if a.key.path[-1] == "personalized_instruction_by_lesson"
    ][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_iready_personalized_instruction_by_lesson_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import assets

    asset = [
        a for a in assets if a.key.path[-1] == "personalized_instruction_by_lesson"
    ][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_iready_instructional_usage_data_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "instructional_usage_data"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_iready_instructional_usage_data_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "instructional_usage_data"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_iready_diagnostic_and_instruction_kippmiami():
    from teamster.code_locations.kippmiami.iready.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "diagnostic_and_instruction"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_iready_diagnostic_and_instruction_kippnj():
    from teamster.code_locations.kippnewark.iready.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "diagnostic_and_instruction"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_deanslist_reconcile_attendance_kipptaf():
    from teamster.code_locations.kipptaf.deanslist.assets import assets
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_DEANSLIST

    asset = [a for a in assets if a.key.path[-1] == "reconcile_attendance"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_deanslist": SSH_RESOURCE_DEANSLIST})


def test_deanslist_reconcile_suspensions_kipptaf():
    from teamster.code_locations.kipptaf.deanslist.assets import assets
    from teamster.code_locations.kipptaf.resources import SSH_RESOURCE_DEANSLIST

    asset = [a for a in assets if a.key.path[-1] == "reconcile_suspensions"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_deanslist": SSH_RESOURCE_DEANSLIST})


def test_adp_payroll_general_ledger_file_kipptaf():
    from teamster.code_locations.kipptaf.adp.payroll.assets import general_ledger_file

    partitions_def = _check.inst(
        obj=general_ledger_file.partitions_def, ttype=MultiPartitionsDefinition
    )

    date_partitions_def = _check.inst(
        obj=partitions_def.get_partitions_def_for_dimension("date"),
        ttype=DynamicPartitionsDefinition,
    )

    partitions_def_name = _check.not_none(value=date_partitions_def.name)

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=partitions_def_name, partition_keys=["20240229"]
        )

        _test_asset(
            asset=general_ledger_file,
            ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
            instance=instance,
        )
