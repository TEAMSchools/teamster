import random

from dagster import (
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    _check,
    instance_for_test,
    materialize,
)

from teamster.code_locations.kipptaf.adp.payroll.assets import general_ledger_file
from teamster.libraries.core.resources import SSH_COUCHDROP, get_io_manager_gcs_avro


def _test_asset(asset, partition_key=None, instance=None):
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
            "ssh_couchdrop": SSH_COUCHDROP,
        },
    )

    assert result.success

    asset_check_evaluation = result.get_asset_check_evaluations()[0]

    extras = asset_check_evaluation.metadata.get("extras")

    assert extras is not None
    assert extras.text == ""


def test_adp_payroll_general_ledger_file_kipptaf():
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
            partitions_def_name=partitions_def_name, partition_keys=["20240731"]
        )

        _test_asset(
            asset=general_ledger_file, instance=instance, partition_key="20240731|2Z3"
        )
