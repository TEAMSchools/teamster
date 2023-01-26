from dagster import build_op_context, config_from_files, with_resources

from teamster.core.powerschool.db.assets import build_powerschool_table_asset
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource

CODE_LOCATION = "test"
PARTITIONS_START_DATE = "2002-07-01T00:00:00.000000-0400"

powerschool_table_asset = with_resources(
    definitions=[build_powerschool_table_asset(asset_name="schools")],
    resource_defs={
        "ps_db": oracle.configured(
            config_from_files(
                ["src/teamster/core/resources/config/db_powerschool.yaml"]
            )
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files(
                ["src/teamster/core/resources/config/ssh_powerschool.yaml"]
            )
        ),
    },
)[0]


def test_powerschool_table_asset():
    powerschool_table_asset(build_op_context())
