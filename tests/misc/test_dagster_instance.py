from teamster.core.utils.functions import get_dagster_cloud_instance
from teamster.kipptaf.dbt.assets import dbt_assets


def _add_dynamic_partitions(partitions_def_name: str, partition_keys: list):
    instance = get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")

    instance.add_dynamic_partitions(
        partitions_def_name=partitions_def_name, partition_keys=partition_keys
    )


def _delete_dynamic_partitions(partitions_def_name: str):
    instance = get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")

    dynamic_partitions = instance.get_dynamic_partitions(partitions_def_name)

    for partition_key in dynamic_partitions:
        instance.delete_dynamic_partition(
            partitions_def_name=partitions_def_name, partition_key=partition_key
        )


def _test_delete_dynamic_partitions_alchemer():
    _delete_dynamic_partitions("kipptaf_alchemer_survey_response")


def test_code_versions():
    instance = get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")

    latest_code_versions = instance.get_latest_materialization_code_versions(
        asset_keys=list(dbt_assets.code_versions_by_key.keys())
    )

    for asset_key, current_code_version in dbt_assets.code_versions_by_key.items():
        latest_code_version = latest_code_versions.get(asset_key)

        if current_code_version != latest_code_version:
            print(asset_key, current_code_version, latest_code_version)
