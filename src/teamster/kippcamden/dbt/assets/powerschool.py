import pendulum
from dagster_dbt import load_assets_from_dbt_project

from teamster.core.dbt.assets import build_dbt_external_source_asset
from teamster.kippcamden import CODE_LOCATION
from teamster.kippcamden.powerschool.db.assets import (
    hourly_partitions_def,
    whenmodified_assets,
)


def partition_key_to_vars(partition_key):
    partition_key_datetime = pendulum.parser.parse(text=partition_key)
    return {
        "_file_name": (
            f"dt={partition_key_datetime.date()}/"
            f"{partition_key_datetime.format(fmt='HH')}"
        )
    }


assignmentcategoryassoc = load_assets_from_dbt_project(
    project_dir="teamster-dbt",
    profiles_dir="teamster-dbt",
    select="assignmentcategoryassoc+",
    key_prefix=[CODE_LOCATION, "dbt"],
    source_key_prefix=[CODE_LOCATION, "dbt"],
    partitions_def=hourly_partitions_def,
    partition_key_to_vars_fn=partition_key_to_vars,
)

src_assignmentcategoryassoc = build_dbt_external_source_asset(whenmodified_assets[0])

__all__ = assignmentcategoryassoc + [src_assignmentcategoryassoc]
