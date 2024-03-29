import pathlib

from dagster import (
    MonthlyPartitionsDefinition,
    MultiPartitionsDefinition,
    StaticPartitionsDefinition,
    config_from_files,
)

from teamster.core.deanslist.assets import (
    build_deanslist_multi_partition_asset,
    build_deanslist_static_partition_asset,
)
from teamster.core.utils.classes import FiscalYearPartitionsDefinition

from .. import CODE_LOCATION, LOCAL_TIMEZONE

static_partitions_def = StaticPartitionsDefinition(["120", "126", "130", "473", "652"])

config_dir = pathlib.Path(__file__).parent / "config"

static_partition_assets = [
    build_deanslist_static_partition_asset(
        code_location=CODE_LOCATION, partitions_def=static_partitions_def, **endpoint
    )
    for endpoint in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

multi_partition_monthly_assets = [
    build_deanslist_multi_partition_asset(
        code_location=CODE_LOCATION,
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "date": MonthlyPartitionsDefinition(
                    start_date="2016-07-01", timezone=LOCAL_TIMEZONE.name, end_offset=1
                ),
                "school": static_partitions_def,
            }
        ),
        **endpoint,
    )
    for endpoint in config_from_files(
        [f"{config_dir}/multi-partition-monthly-assets.yaml"]
    )["endpoints"]
]

multi_partition_fiscal_assets = [
    build_deanslist_multi_partition_asset(
        code_location=CODE_LOCATION,
        partitions_def=MultiPartitionsDefinition(
            partitions_defs={
                "date": FiscalYearPartitionsDefinition(
                    start_date="2016-07-01",
                    start_month=7,
                    timezone=LOCAL_TIMEZONE.name,
                    end_offset=1,
                ),
                "school": static_partitions_def,
            }
        ),
        **endpoint,
    )
    for endpoint in config_from_files(
        [f"{config_dir}/multi-partition-fiscal-assets.yaml"]
    )["endpoints"]
]

_all = [
    *static_partition_assets,
    *multi_partition_monthly_assets,
    *multi_partition_fiscal_assets,
]
