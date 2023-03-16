from dagster import build_op_context, config_from_files, with_resources
from dagster_gcp.gcs import gcs_resource

from teamster.core.resources.deanslist import deanslist_resource
from teamster.core.resources.google import gcs_avro_io_manager
from teamster.test.deanslist import assets

deanslist_endpoint_asset = with_resources(
    definitions=[*assets.__all__],
    resource_defs={
        "deanslist": deanslist_resource.configured(
            config_from_files(
                [
                    "src/teamster/core/resources/config/deanslist.yaml",
                    "src/teamster/test/resources/config/deanslist.yaml",
                ]
            )
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
        "gcs_avro_io": gcs_avro_io_manager.configured(
            config_from_files(["src/teamster/test/resources/config/io.yaml"])
        ),
    },
)


def test_powerschool_table_asset():
    for asset in deanslist_endpoint_asset:
        asset(build_op_context())
