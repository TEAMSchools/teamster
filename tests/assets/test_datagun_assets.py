import random

from dagster import AssetsDefinition, materialize

from teamster.core.resources import BIGQUERY_RESOURCE, GCS_RESOURCE, SSH_COUCHDROP
from teamster.core.utils.functions import get_dagster_cloud_instance


def _test_asset(asset: AssetsDefinition, instance=None):
    partition_keys = asset.partitions_def.get_partition_keys(
        dynamic_partitions_store=instance
    )

    result = materialize(
        assets=[asset],
        partition_key=partition_keys[random.randint(a=0, b=(len(partition_keys) - 1))],
        instance=instance,
        resources={
            "gcs": GCS_RESOURCE,
            "db_bigquery": BIGQUERY_RESOURCE,
            "ssh_couchdrop": SSH_COUCHDROP,
        },
    )

    assert result.success


def test_intacct_extract_asset():
    from teamster.kipptaf.datagun.assets import intacct_extract_asset

    instance = get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")

    _test_asset(asset=intacct_extract_asset, instance=instance)
