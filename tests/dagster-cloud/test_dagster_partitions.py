from teamster.core.utils.functions import get_dagster_cloud_instance


def _add_dynamic_partitions(partitions_def_name: str, partition_keys: list):
    instance = get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")

    instance.add_dynamic_partitions(
        partitions_def_name=partitions_def_name, partition_keys=partition_keys
    )
