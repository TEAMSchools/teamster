import random

from dagster import AssetsDefinition, PartitionsDefinition, materialize

# trunk-ignore(pyright/reportPrivateImportUsage)
from dagster._core.events import StepMaterializationData
from dagster_shared import check

# from teamster.code_locations.kipptaf.resources import ZENDESK_RESOURCE
# from teamster.code_locations.kipptaf.zendesk.assets import ticket_metrics_archive
from teamster.core.resources import get_io_manager_gcs_file


def _test_asset(asset: AssetsDefinition, partition_key: str | None = None):
    if partition_key is None:
        partitions_def = check.inst(
            obj=asset.partitions_def, ttype=PartitionsDefinition
        )
        partition_keys = partitions_def.get_partition_keys()

        partition_key = partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))]

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_file": get_io_manager_gcs_file("test"),
            # "zendesk": ZENDESK_RESOURCE,
        },
        partition_key=partition_key,
    )

    assert result.success
    asset_materialization_event = result.get_asset_materialization_events()[0]
    event_specific_data = check.inst(
        asset_materialization_event.event_specific_data, StepMaterializationData
    )
    records = check.inst(
        event_specific_data.materialization.metadata["records"].value, int
    )
    assert records > 0


# def test_asset_ticket_metrics_archive():
#     _test_asset(ticket_metrics_archive)
