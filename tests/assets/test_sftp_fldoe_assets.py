import random

from dagster import _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kippmiami.fldoe.assets import eoc, fast, fsa, science
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
            "ssh_couchdrop": SSH_COUCHDROP,
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
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


def test_fldoe_fast_kippmiami():
    _test_asset(asset=fast, partition_key="Grade3FASTELAReading|SY23/PM3")


def test_fldoe_fsa_kippmiami():
    _test_asset(asset=fsa)


def test_fldoe_eoc_kippmiami():
    _test_asset(asset=eoc)


def test_fldoe_science_kippmiami():
    _test_asset(asset=science)
