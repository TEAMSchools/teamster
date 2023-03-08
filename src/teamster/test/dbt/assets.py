import json

import pendulum
from dagster import DynamicPartitionsDefinition
from dagster_dbt import load_assets_from_dbt_manifest

from teamster.core.dbt.assets import build_external_source_asset
from teamster.core.resources.google import parse_date_partition_key
from teamster.test import CODE_LOCATION, deanslist, powerschool

key_prefix = [CODE_LOCATION, "dbt"]

manifest_json_path = f"teamster-dbt/{CODE_LOCATION}/target/manifest.json"
with open(file=manifest_json_path) as f:
    manifest_json = json.load(f)


def partition_key_to_vars(partition_key):
    path = parse_date_partition_key(pendulum.parse(text=partition_key))
    path.append("data")

    return {"partition_path": "/".join(path)}


# powerschool
powerschool_src_assets = [
    build_external_source_asset(a) for a in powerschool.db.assets.__all__
]
# powerschool_nonpartition_stg_assets = build_staging_assets(
#     manifest_json_path=manifest_json_path,
#     key_prefix=key_prefix,
#     assets=powerschool.db.assets.nonpartition_assets,
# )
# powerschool_incremental_stg_assets = build_staging_assets(
#     manifest_json_path=manifest_json_path,
#     key_prefix=key_prefix,
#     assets=powerschool.db.assets.partition_assets,
#     partitions_def=powerschool.db.assets.dynamic_partitions_def,
# )

powerschool_incremental_stg_assets = load_assets_from_dbt_manifest(
    manifest_json=manifest_json,
    # select=f"stg_{a.key.path[-2]}__{a.key.path[-1]}+",
    key_prefix=key_prefix,
    source_key_prefix=key_prefix[:2],
    partitions_def=DynamicPartitionsDefinition(name="foo"),
    partition_key_to_vars_fn=partition_key_to_vars,
)

# deanslist
deanslist_src_assets = [
    build_external_source_asset(a) for a in deanslist.assets.__all__
]

__all__ = [
    *powerschool_src_assets,
    *powerschool_incremental_stg_assets,
    # *powerschool_nonpartition_stg_assets,
    *deanslist_src_assets,
]
