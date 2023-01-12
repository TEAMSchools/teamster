from dagster import HourlyPartitionsDefinition

from teamster.core.powerschool.db.assets import (
    generate_powerschool_assets,
    table_asset_factory,
)
from teamster.core.utils.variables import LOCAL_TIME_ZONE

hourly_partition = HourlyPartitionsDefinition(
    start_date="2018-07-01T00:00:00.000000-0400",
    timezone=str(LOCAL_TIME_ZONE),
    fmt="%Y-%m-%dT%H:%M:%S.%f%z",
)

core_ps_db_assets = generate_powerschool_assets(partition=hourly_partition)

local_ps_db_assets = []
for table_name in [
    "u_clg_et_stu",
    "u_clg_et_stu_alt",
    "u_def_ext_students",
    "u_studentsuserfields",
]:
    local_ps_db_assets.append(
        table_asset_factory(
            asset_name=table_name,
            where={"column": "whenmodified"},
            partitions_def=hourly_partition,
        )
    )
