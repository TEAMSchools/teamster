import json

import pendulum
from dagster_dbt import load_assets_from_dbt_manifest

from teamster.core.dbt.assets import build_dbt_external_source_asset
from teamster.kippcamden import CODE_LOCATION
from teamster.kippcamden.powerschool.db.assets import (
    all_assets,
    hourly_partitions_def,
    partition_assets,
)


def partition_key_to_vars(partition_key):
    partition_key_datetime = pendulum.parser.parse(text=partition_key)
    return {
        "partition_path": (
            f"dt={partition_key_datetime.date()}/"
            f"{partition_key_datetime.format(fmt='HH')}"
        )
    }


src_assets = [build_dbt_external_source_asset(a) for a in all_assets]

with open(file="teamster-dbt/kippcamden/target/manifest.json") as f:
    manifest_json = json.load(f)

incremental_stg_assets = [
    load_assets_from_dbt_manifest(
        manifest_json=manifest_json,
        select=f"stg_powerschool__{a.key.path[-1]}+",
        key_prefix=[CODE_LOCATION, "dbt", "powerschool"],
        source_key_prefix=[CODE_LOCATION, "dbt"],
        partitions_def=hourly_partitions_def,
        partition_key_to_vars_fn=partition_key_to_vars,
    )
    for a in partition_assets
]

__all__ = src_assets + [
    asset for asset_list in incremental_stg_assets for asset in asset_list
]
