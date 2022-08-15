from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource

from teamster.common.graphs.powerschool.api import run_queries
from teamster.common.resources.google import gcs_file_manager
from teamster.common.resources.powerschool import powerschool_api

powerschool_api_extract = run_queries.to_job(
    name="powerschool_extract",
    resource_defs={
        "powerschool": powerschool_api,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/common/config/powerschool/api/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/kippnewark/config/powerschool/api/query-default.yaml",
        ]
    ),
)

powerschool_api_resync = run_queries.to_job(
    name="powerschool_resync",
    resource_defs={
        "powerschool": powerschool_api,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/common/config/powerschool/api/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/kippnewark/config/powerschool/api/query-resync.yaml",
        ]
    ),
)

powerschool_api_resync_assignmentscore = run_queries.to_job(
    name="powerschool_resync_assignmentscore",
    resource_defs={
        "powerschool": powerschool_api,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/common/config/powerschool/api/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            # trunk-ignore(flake8/E501)
            "./teamster/kippnewark/config/powerschool/api/query-resync-assignmentscore.yaml",
        ]
    ),
)

__all__ = [
    "powerschool_api_extract",
    "powerschool_api_resync",
    "powerschool_api_resync_assignmentscore",
]
