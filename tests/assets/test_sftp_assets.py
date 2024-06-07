import random

from dagster import (
    DynamicPartitionsDefinition,
    EnvVar,
    MultiPartitionsDefinition,
    TextMetadataValue,
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
    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = _check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )
    assert records > 0
    extras = _check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
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


def test_pearson_njgpa_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import njgpa

    _test_asset(asset=njgpa, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_njgpa_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import njgpa

    _test_asset(asset=njgpa, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_njsla_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "njsla"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_njsla_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "njsla"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_njsla_science_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "njsla_science"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_njsla_science_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "njsla_science"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_parcc_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "parcc"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_parcc_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "parcc"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_performance_management_observation_details_kipptaf():
    from teamster.code_locations.kipptaf.performance_management.assets import (
        observation_details,
    )

    _test_asset(
        asset=observation_details, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP}
    )


def test_renlearn_accelerated_reader_kippnj():
    from teamster.code_locations.kippnewark.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "accelerated_reader"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_renlearn": SSHResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPNJ"),
                password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPNJ"),
            )
        },
    )


def test_renlearn_accelerated_reader_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "accelerated_reader"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_renlearn": SSHResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPMIAMI"),
                password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPMIAMI"),
            )
        },
    )


def test_renlearn_star_kippnj():
    from teamster.code_locations.kippnewark.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_renlearn": SSHResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPNJ"),
                password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPNJ"),
            )
        },
    )


def test_renlearn_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_renlearn": SSHResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPMIAMI"),
                password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPMIAMI"),
            )
        },
    )


def test_renlearn_star_skill_area_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star_skill_area"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_renlearn": SSHResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPMIAMI"),
                password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPMIAMI"),
            )
        },
    )


def test_renlearn_star_dashboard_standards_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "star_dashboard_standards"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_renlearn": SSHResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPMIAMI"),
                password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPMIAMI"),
            )
        },
    )


def test_renlearn_fast_star_kippmiami():
    from teamster.code_locations.kippmiami.renlearn.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "fast_star"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_renlearn": SSHResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar("RENLEARN_SFTP_USERNAME_KIPPMIAMI"),
                password=EnvVar("RENLEARN_SFTP_PASSWORD_KIPPMIAMI"),
            )
        },
    )


def test_fldoe_fast_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "fast"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_fldoe_fsa_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "fsa"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_fldoe_eoc_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "eoc"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_fldoe_science_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "science"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


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


def test_titan_person_data_kippnewark():
    from teamster.code_locations.kippnewark.titan.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "person_data"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_titan": SSHResource(
                remote_host="sftp.titank12.com",
                username=EnvVar("TITAN_SFTP_USERNAME_KIPPNEWARK"),
                password=EnvVar("TITAN_SFTP_PASSWORD_KIPPNEWARK"),
            )
        },
    )


def test_titan_person_data_kippcamden():
    from teamster.code_locations.kippnewark.titan.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "person_data"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_titan": SSHResource(
                remote_host="sftp.titank12.com",
                username=EnvVar("TITAN_SFTP_USERNAME_KIPPCAMDEN"),
                password=EnvVar("TITAN_SFTP_PASSWORD_KIPPCAMDEN"),
            )
        },
    )


def test_titan_income_form_data_kippnewark():
    from teamster.code_locations.kippnewark.titan.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "income_form_data"][0]

    _test_asset(
        asset=asset,
        ssh_resource={
            "ssh_titan": SSHResource(
                remote_host="sftp.titank12.com",
                username=EnvVar("TITAN_SFTP_USERNAME_KIPPNEWARK"),
                password=EnvVar("TITAN_SFTP_PASSWORD_KIPPNEWARK"),
            )
        },
    )


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


def test_pearson_student_list_report_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "student_list_report"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_pearson_student_list_report_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import assets

    asset = [a for a in assets if a.key.path[-1] == "student_list_report"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})
