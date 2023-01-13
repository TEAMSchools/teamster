from teamster.core.powerschool.db.assets import (
    generate_powerschool_assets,
    table_asset_factory,
)

PARTITIONS_START_DATE = "2018-07-01T00:00:00.000000-0400"

core_ps_db_assets = generate_powerschool_assets(
    partition_start_date=PARTITIONS_START_DATE
)

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
            partition_start_date=PARTITIONS_START_DATE,
        )
    )
