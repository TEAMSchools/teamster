from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource

from teamster.common.graphs.powerschool import run_queries
from teamster.common.resources.google import gcs_file_manager
from teamster.common.resources.powerschool import powerschool

powerschool_extract = run_queries.to_job(
    name="powerschool_extract",
    resource_defs={
        "powerschool": powerschool,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/common/config/powerschool/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/kippcamden/config/powerschool/query-default.yaml",
        ]
    ),
)

powerschool_resync = run_queries.to_job(
    name="powerschool_resync",
    resource_defs={
        "powerschool": powerschool,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/common/config/powerschool/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/kippcamden/config/powerschool/query-resync.yaml",
        ]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {
                    "limits": {
                        "cpu": "10000m",
                        "memory": "10Gi",
                        "ephemeral-storage": "1Gi",
                    }
                }
            },
        }
    },
)

powerschool_resync_assignmentscore = run_queries.to_job(
    name="powerschool_resync_assignmentscore",
    resource_defs={
        "powerschool": powerschool,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/common/config/powerschool/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/kippcamden/config/powerschool/query-resync-assignmentscore.yaml",
        ]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {
                    "limits": {
                        "cpu": "10000m",
                        "memory": "10Gi",
                        "ephemeral-storage": "1Gi",
                    }
                }
            },
        }
    },
)

__all__ = [
    "powerschool_extract",
    "powerschool_resync",
    "powerschool_resync_assignmentscore",
]
