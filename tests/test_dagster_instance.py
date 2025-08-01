import re

from dagster import DagsterInstance


def _add_dynamic_partitions(partitions_def_name: str, partition_keys: list):
    instance = DagsterInstance.from_config(
        config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
    )

    instance.add_dynamic_partitions(
        partitions_def_name=partitions_def_name, partition_keys=partition_keys
    )


def _delete_dynamic_partitions(partitions_def_name: str, pattern: str):
    instance = DagsterInstance.from_config(
        config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
    )

    dynamic_partitions = instance.get_dynamic_partitions(partitions_def_name)

    for partition_key in dynamic_partitions:
        if re.match(pattern=pattern, string=partition_key):
            instance.delete_dynamic_partition(
                partitions_def_name=partitions_def_name, partition_key=partition_key
            )


def _test_delete_dynamic_partitions_alchemer():
    _delete_dynamic_partitions(
        partitions_def_name="kipptaf_alchemer_survey_response", pattern=r"\d+_\d{2,}\.0"
    )


def test_code_versions():
    from teamster.code_locations.kipptaf._dbt.assets import dbt_assets

    instance = DagsterInstance.from_config(
        config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
    )

    latest_code_versions = instance.get_latest_materialization_code_versions(
        asset_keys=list(dbt_assets.code_versions_by_key.keys())
    )

    for asset_key, current_code_version in dbt_assets.code_versions_by_key.items():
        latest_code_version = latest_code_versions.get(asset_key)

        if current_code_version != latest_code_version:
            print(asset_key, current_code_version, latest_code_version)
