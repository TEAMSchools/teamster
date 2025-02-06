from dagster import TextMetadataValue, _check, materialize
from dagster._core.events import StepMaterializationData

from teamster.code_locations.kipptaf.coupa.assets import assets as COUPA_ASSETS
from teamster.code_locations.kipptaf.resources import COUPA_RESOURCE
from teamster.core.resources import get_io_manager_gcs_avro


def _test_asset(selection):
    result = materialize(
        assets=COUPA_ASSETS,
        selection=selection,
        resources={
            "io_manager_gcs_avro": get_io_manager_gcs_avro(
                code_location="test", test=True
            ),
            "coupa": COUPA_RESOURCE,
        },
    )

    assert result.success

    asset_materialization_event = result.get_asset_materialization_events()[0]

    event_specific_data = _check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = _check.inst(
        event_specific_data.materialization.metadata["record_count"].value, int
    )
    assert records > 0

    extras = _check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )
    assert extras.text == ""


def test_asset_coupa_addresses():
    _test_asset("kipptaf/coupa/addresses")


def test_asset_coupa_users():
    _test_asset("kipptaf/coupa/users")
