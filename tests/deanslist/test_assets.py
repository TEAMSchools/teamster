from dagster import build_op_context, config_from_files, with_resources
from dagster_gcp.gcs import gcs_resource

from teamster.core.resources.deanslist import deanslist_resource
from teamster.core.resources.google import gcs_avro_io_manager
from teamster.staging.deanslist import assets

deanslist_endpoint_asset = with_resources(
    definitions=[*assets.__all__],
    resource_defs={
        "deanslist": deanslist_resource.configured(
            config_from_files(["src/teamster/core/config/resources/deanslist.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files(["tests/config/resources/gcs.yaml"])
        ),
        "gcs_avro_io": gcs_avro_io_manager.configured(
            config_from_files(["tests/config/resources/io.yaml"])
        ),
    },
)


def test_deanslist_endpoint_asset():
    for asset in deanslist_endpoint_asset:
        asset(build_op_context())
