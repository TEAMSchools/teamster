import random

from dagster import materialize

from teamster.libraries.core.resources import SSH_COUCHDROP, get_io_manager_gcs_avro


def _test_asset(asset, partition_key=None):
    if partition_key is not None:
        pass
    elif asset.partitions_def is not None:
        partition_keys = asset.partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]
    else:
        partition_key = None

    result = materialize(
        assets=[asset],
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
