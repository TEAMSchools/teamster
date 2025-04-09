from dagster import TextMetadataValue, materialize

# trunk-ignore(pyright/reportPrivateImportUsage)
from dagster._core.events import StepMaterializationData
from dagster_dlt import DagsterDltResource
from dagster_shared import check

from teamster.code_locations.kipptaf._dlt import assets


def _test_dlt_assets(assets, selection):
    result = materialize(
        assets=assets, selection=selection, resources={"dlt": DagsterDltResource()}
    )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    extras = check.inst(
        obj=result.get_asset_check_evaluations()[0].metadata.get("extras"),
        ttype=TextMetadataValue,
    )

    event_specific_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )

    records = check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )

    assert records > 0
    assert extras.text == ""


def test_dlt_illuminate_codes():
    _test_dlt_assets(
        assets=assets, selection=["kipptaf/dlt/illuminate/codes/dna_scopes"]
    )
