import random

from dagster import AssetsDefinition, materialize

from teamster.core.resources import get_io_manager_gcs_file
from teamster.kipptaf.resources import ZENDESK_RESOURCE
from teamster.kipptaf.zendesk.assets import ticket_metrics_archive


def _test_asset(asset: AssetsDefinition):
    partition_keys = asset.partitions_def.get_partition_keys()

    result = materialize(
        assets=[asset],
        resources={
            "io_manager_gcs_file": get_io_manager_gcs_file("staging"),
            "zendesk": ZENDESK_RESOURCE,
        },
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
    )

    assert result.success


def test_asset_ticket_metrics_archive():
    _test_asset(ticket_metrics_archive)
