import random

from dagster import (
    AssetsDefinition,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    instance_for_test,
    materialize,
)
from dagster_shared import check


def _test_asset(
    asset: AssetsDefinition, partition_key: str | None = None, instance=None
):
    from teamster.core.resources import SSH_COUCHDROP, get_io_manager_gcs_avro

    if partition_key is None and asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        instance=instance,
        partition_key=partition_key,
        resources={
            "ssh_couchdrop": SSH_COUCHDROP,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_adp_payroll_general_ledger_file_kipptaf():
    from teamster.code_locations.kipptaf.adp.payroll.assets import general_ledger_file

    date_key = "20241130"
    group_code_key = "47S"

    partitions_def = check.inst(
        obj=general_ledger_file.partitions_def, ttype=MultiPartitionsDefinition
    )

    date_partitions_def = check.inst(
        obj=partitions_def.get_partitions_def_for_dimension("date"),
        ttype=DynamicPartitionsDefinition,
    )

    date_partitions_def = check.not_none(value=date_partitions_def.name)

    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=date_partitions_def, partition_keys=[date_key]
        )

        _test_asset(
            asset=general_ledger_file,
            partition_key=f"{date_key}|{group_code_key}",
            instance=instance,
        )


def test_fldoe_fast_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import fast

    _test_asset(asset=fast)


def test_fldoe_eoc_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import eoc

    _test_asset(asset=eoc)


def test_fldoe_science_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import science

    _test_asset(asset=science)


def test_fldoe_fte_kippmiami():
    from teamster.code_locations.kippmiami.fldoe.assets import fte

    _test_asset(asset=fte)


def test_pearson_njgpa_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import njgpa

    _test_asset(asset=njgpa)


def test_pearson_njgpa_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import njgpa

    _test_asset(asset=njgpa)


def test_pearson_njsla_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import njsla

    _test_asset(asset=njsla)


def test_pearson_njsla_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import njsla

    _test_asset(asset=njsla)


def test_pearson_njsla_science_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import njsla_science

    _test_asset(asset=njsla_science)


def test_pearson_njsla_science_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import njsla_science

    _test_asset(asset=njsla_science)


def test_pearson_parcc_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import parcc

    _test_asset(asset=parcc)


def test_pearson_parcc_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import parcc

    _test_asset(asset=parcc)


def test_pearson_student_list_report_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import student_list_report

    _test_asset(asset=student_list_report)


def test_pearson_student_list_report_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import student_list_report

    _test_asset(asset=student_list_report)


def test_pearson_student_test_update_kippnewark():
    from teamster.code_locations.kippnewark.pearson.assets import student_test_update

    _test_asset(asset=student_test_update)


def test_pearson_student_test_update_kippcamden():
    from teamster.code_locations.kippcamden.pearson.assets import student_test_update

    _test_asset(asset=student_test_update)


def test_tableau_view_count_per_view_kipptaf():
    from teamster.code_locations.kipptaf.tableau.assets import view_count_per_view

    _test_asset(asset=view_count_per_view)


def test_collegeboard_psat_kipptaf_psatnm():
    from teamster.code_locations.kipptaf.collegeboard.assets import psat

    _test_asset(asset=psat)


def test_collegeboard_psat_kipptaf_psat10():
    from teamster.code_locations.kipptaf.collegeboard.assets import psat

    _test_asset(asset=psat)


def test_collegeboard_ap_kipptaf():
    from teamster.code_locations.kipptaf.collegeboard.assets import ap

    _test_asset(asset=ap)
