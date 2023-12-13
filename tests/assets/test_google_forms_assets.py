import random

from dagster import AssetsDefinition, materialize

from teamster.core.resources import get_io_manager_gcs_avro
from teamster.kipptaf.google.forms.assets import form, responses
from teamster.kipptaf.resources import GOOGLE_FORMS_RESOURCE


def _test_asset(asset: AssetsDefinition):
    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro("staging"),
            "google_forms": GOOGLE_FORMS_RESOURCE,
        },
    )

    assert result.success
    assert (
        result.get_asset_materialization_events()[0]
        .event_specific_data.materialization.metadata["record_count"]
        .value
        > 0
    )


def test_asset_google_forms_form():
    _test_asset(form)


def test_asset_google_forms_responses():
    _test_asset(responses)
