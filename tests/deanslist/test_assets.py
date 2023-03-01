from dagster import build_op_context, config_from_files, with_resources
from dagster_gcp.gcs import gcs_resource

from teamster.core.resources.deanslist import deanslist_resource
from teamster.core.resources.google import gcs_avro_io_manager
from teamster.test.deanslist import assets

CODE_LOCATION = "test"

deanslist_endpoint_asset = with_resources(
    definitions=[*assets.nonpartition_assets],
    resource_defs={
        "deanslist": deanslist_resource.configured(
            config_from_files(
                [
                    "src/teamster/core/resources/config/deanslist.yaml",
                    f"src/teamster/{CODE_LOCATION}/resources/config/deanslist.yaml",
                ]
            )
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["src/teamster/core/resources/config/gcs.yaml"])
        ),
        "gcs_avro_io": gcs_avro_io_manager.configured(
            config_from_files(
                [f"src/teamster/{CODE_LOCATION}/resources/config/io.yaml"]
            )
        ),
    },
)


def test_powerschool_table_asset():
    deanslist_endpoint_asset[0](build_op_context())
