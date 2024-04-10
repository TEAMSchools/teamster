import random

from dagster import EnvVar, instance_for_test, materialize

from teamster.core.resources import SSH_COUCHDROP, SSH_IREADY, get_io_manager_gcs_avro
from teamster.core.ssh.resources import SSHResource
from teamster.kipptaf.resources import SSH_RESOURCE_ACHIEVE3K, SSH_RESOURCE_DEANSLIST


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
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            **ssh_resource,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["records"]  # type: ignore
        .value
        > 0
    )
    assert result.get_asset_check_evaluations()[0].metadata.get("extras").text == ""


def test_asset_edplan_kippcamden():
    from teamster.kippcamden.edplan.assets import njsmart_powerschool

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


def test_asset_edplan_kippnewark():
    from teamster.kippnewark.edplan.assets import njsmart_powerschool

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


def test_asset_pearson_njgpa_kippcamden():
    from teamster.kippcamden.pearson.assets import njgpa

    _test_asset(asset=njgpa, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_pearson_njgpa_kippnewark():
    from teamster.kippnewark.pearson.assets import njgpa

    _test_asset(asset=njgpa, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_pearson_njsla_kippnewark():
    from teamster.kippnewark.pearson.assets import all_assets

    asset = [a for a in all_assets if a.key.path[-1] == "njsla"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_pearson_njsla_kippcamden():
    from teamster.kippcamden.pearson.assets import all_assets

    asset = [a for a in all_assets if a.key.path[-1] == "njsla"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_pearson_njsla_science_kippnewark():
    from teamster.kippnewark.pearson.assets import all_assets

    asset = [a for a in all_assets if a.key.path[-1] == "njsla_science"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_pearson_njsla_science_kippcamden():
    from teamster.kippcamden.pearson.assets import all_assets

    asset = [a for a in all_assets if a.key.path[-1] == "njsla_science"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_pearson_parcc_kippnewark():
    from teamster.kippnewark.pearson.assets import all_assets

    asset = [a for a in all_assets if a.key.path[-1] == "parcc"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_pearson_parcc_kippcamden():
    from teamster.kippcamden.pearson.assets import all_assets

    asset = [a for a in all_assets if a.key.path[-1] == "parcc"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_renlearn_accelerated_reader_kippnj():
    from teamster.kippnewark.renlearn.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "accelerated_reader"][0]

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


def test_asset_renlearn_accelerated_reader_kippmiami():
    from teamster.kippmiami.renlearn.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "accelerated_reader"][0]

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


def test_asset_renlearn_star_kippnj():
    from teamster.kippnewark.renlearn.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "star"][0]

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


def test_asset_renlearn_star_kippmiami():
    from teamster.kippmiami.renlearn.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "star"][0]

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


def test_asset_renlearn_star_skill_area_kippmiami():
    from teamster.kippmiami.renlearn.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "star_skill_area"][0]

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


def test_asset_renlearn_star_dashboard_standards_kippmiami():
    from teamster.kippmiami.renlearn.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "star_dashboard_standards"][0]

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


def test_asset_renlearn_fast_star_kippmiami():
    from teamster.kippmiami.renlearn.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "fast_star"][0]

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


def test_asset_fldoe_fast_kippmiami():
    from teamster.kippmiami.fldoe.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "fast"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_fldoe_fsa_kippmiami():
    from teamster.kippmiami.fldoe.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "fsa"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_couchdrop": SSH_COUCHDROP})


def test_asset_iready_diagnostic_results_kippmiami():
    from teamster.kippmiami.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "diagnostic_results"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_iready_diagnostic_results_kippnj():
    from teamster.kippnewark.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "diagnostic_results"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_iready_personalized_instruction_by_lesson_kippmiami():
    from teamster.kippmiami.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "personalized_instruction_by_lesson"][
        0
    ]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_iready_personalized_instruction_by_lesson_kippnj():
    from teamster.kippnewark.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "personalized_instruction_by_lesson"][
        0
    ]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_iready_instructional_usage_data_kippmiami():
    from teamster.kippmiami.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "instructional_usage_data"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_iready_instructional_usage_data_kippnj():
    from teamster.kippnewark.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "instructional_usage_data"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_iready_diagnostic_and_instruction_kippmiami():
    from teamster.kippmiami.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "diagnostic_and_instruction"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_iready_diagnostic_and_instruction_kippnj():
    from teamster.kippnewark.iready.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "diagnostic_and_instruction"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_iready": SSH_IREADY})


def test_asset_titan_person_data_kippnewark():
    from teamster.kippnewark.titan.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "person_data"][0]

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


def test_asset_titan_person_data_kippcamden():
    from teamster.kippnewark.titan.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "person_data"][0]

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


def test_asset_titan_income_form_data_kippnewark():
    from teamster.kippnewark.titan.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "income_form_data"][0]

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


def test_asset_achieve3k_students_kipptaf():
    from teamster.kipptaf.achieve3k.assets import students

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=students.partitions_def.name,  # type: ignore
            partition_keys=["2024-04-01"],
        )

        _test_asset(
            asset=students,
            ssh_resource={"ssh_achieve3k": SSH_RESOURCE_ACHIEVE3K},
            instance=instance,
        )


def test_asset_deanslist_reconcile_attendance_kipptaf():
    from teamster.kipptaf.deanslist.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "reconcile_attendance"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_deanslist": SSH_RESOURCE_DEANSLIST})


def test_asset_deanslist_reconcile_suspensions_kipptaf():
    from teamster.kipptaf.deanslist.assets import _all

    asset = [a for a in _all if a.key.path[-1] == "reconcile_suspensions"][0]

    _test_asset(asset=asset, ssh_resource={"ssh_deanslist": SSH_RESOURCE_DEANSLIST})


def test_asset_adp_payroll_general_ledger_file_kipptaf():
    from teamster.kipptaf.adp.payroll.assets import general_ledger_file

    partitions_def_name = (
        general_ledger_file.partitions_def.get_partitions_def_for_dimension("date").name  # type: ignore
    )

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=partitions_def_name, partition_keys=["20240229"]
        )

        _test_asset(
            asset=general_ledger_file,
            ssh_resource={"ssh_couchdrop": SSH_COUCHDROP},
            instance=instance,
            # partition_key="20240229|2Z3",
        )


""" cannot test in dev: IP filter
def test_asset_adp_workforce_now_pension_and_benefits_enrollments():
    from teamster.kipptaf.adp.workforce_now.schema import ASSET_FIELDS

    _test_build_asset(
        asset_key=["adp_workforce_now", "pension_and_benefits_enrollments"],
        remote_dir=".",
        remote_file_regex=r"pension_and_benefits_enrollments\.csv",
        asset_fields=ASSET_FIELDS,
        ssh_resource={"ssh_adp_workforce_now": SSH_ADP_WORKFORCE_NOW},
    )


def test_asset_adp_workforce_now_comprehensive_benefits_report():
    from teamster.kipptaf.adp.workforce_now.schema import ASSET_FIELDS

    _test_build_asset(
        asset_key=["adp_workforce_now", "comprehensive_benefits_report"],
        remote_dir=".",
        remote_file_regex=r"comprehensive_benefits_report\.csv",
        asset_fields=ASSET_FIELDS,
        ssh_resource={"ssh_adp_workforce_now": SSH_ADP_WORKFORCE_NOW},
    )


def test_asset_adp_workforce_now_additional_earnings_report():
    from teamster.kipptaf.adp.workforce_now.schema import ASSET_FIELDS

    _test_build_asset(
        asset_key=["adp_workforce_now", "additional_earnings_report"],
        remote_dir=".",
        remote_file_regex=r"additional_earnings_report\.csv",
        asset_fields=ASSET_FIELDS,
        ssh_resource={"ssh_adp_workforce_now": SSH_ADP_WORKFORCE_NOW},
    )
"""

""" retired
def test_asset_clever_daily_participation():
    from teamster.kipptaf.clever.schema import ASSET_FIELDS

    remote_dir = "daily-participation"

    asset_name = remote_dir.replace("-", "_")

    partitions_def_name = f"staging__clever_reports__date__{asset_name}"

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=partitions_def_name, partition_keys=["2023-12-05"]
        )

        _test_build_asset(
            asset_key=["clever_reports", asset_name],
            remote_dir=remote_dir,
            remote_file_regex=rf"(?P<date>\d{4}-\d{2}-\d{2})-{remote_dir}-(?P<type>\w+)\.csv",
            asset_fields=ASSET_FIELDS,
            ssh_resource={"ssh_clever_reports": SSH_RESOURCE_CLEVER_REPORTS},
            partitions_def=MultiPartitionsDefinition(
                {
                    "date": DynamicPartitionsDefinition(name=partitions_def_name),
                    "type": StaticPartitionsDefinition(
                        ["staff", "students", "teachers"]
                    ),
                }
            ),
            instance=instance,
        )


def test_asset_clever_resource_usage():
    from teamster.kipptaf.clever.schema import ASSET_FIELDS

    remote_dir = "resource-usage"

    asset_name = remote_dir.replace("-", "_")

    partitions_def_name = f"staging__clever_reports__date__{asset_name}"

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=partitions_def_name, partition_keys=["2023-12-05"]
        )

        _test_build_asset(
            asset_key=["clever_reports", asset_name],
            remote_dir=remote_dir,
            remote_file_regex=rf"(?P<date>\d{4}-\d{2}-\d{2})-{remote_dir}-(?P<type>\w+)\.csv",
            asset_fields=ASSET_FIELDS,
            ssh_resource={"ssh_clever_reports": SSH_RESOURCE_CLEVER_REPORTS},
            partitions_def=MultiPartitionsDefinition(
                {
                    "date": DynamicPartitionsDefinition(name=partitions_def_name),
                    "type": StaticPartitionsDefinition(
                        ["staff", "students", "teachers"]
                    ),
                }
            ),
            instance=instance,
        )
"""
