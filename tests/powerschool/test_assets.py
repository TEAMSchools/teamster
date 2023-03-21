from dagster import build_op_context, config_from_files, with_resources
from dagster_gcp.gcs import gcs_resource
from dagster_ssh import ssh_resource

from teamster.core.powerschool.assets import build_powerschool_table_asset
from teamster.core.resources.google import gcs_filepath_io_manager
from teamster.core.resources.sqlalchemy import oracle

CODE_LOCATION = "test"
PARTITIONS_START_DATE = "2002-07-01T00:00:00.000000"

powerschool_table_asset = with_resources(
    definitions=[
        build_powerschool_table_asset(asset_name="schools", code_location=CODE_LOCATION)
    ],
    resource_defs={
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/config/resources/gcs.yaml"])
        ),
        "ps_db": oracle.configured(
            config_from_files(
                ["src/teamster/core/config/resources/db_powerschool.yaml"]
            )
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files(
                ["src/teamster/core/config/resources/ssh_powerschool.yaml"]
            )
        ),
        "gcs_fp_io": gcs_filepath_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/config/resources/io.yaml"]
            )
        ),
    },
)[0]


def test_powerschool_table_asset():
    powerschool_table_asset(build_op_context())
