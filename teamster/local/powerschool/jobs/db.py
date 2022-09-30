from dagster import config_from_files
from dagster_gcp.gcs import gcs_file_manager, gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource
from teamster.local.powerschool.graphs.db import sync_extensions

powerschool_db_sync_extensions = sync_extensions.to_job(
    name="powerschool_db_sync_extensions",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": oracle,
        "ssh": ssh_resource,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/core/resources/config/google.yaml",
            "./teamster/core/powerschool/config/db/resource.yaml",
            "./teamster/local/powerschool/config/db/query-sync-extensions.yaml",
        ]
    ),
)

powerschool_db_resync_extensions = sync_extensions.to_job(
    name="powerschool_db_resync_extensions",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": oracle,
        "ssh": ssh_resource,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/core/resources/config/google.yaml",
            "./teamster/core/powerschool/config/db/resource.yaml",
            "./teamster/local/powerschool/config/db/query-resync-extensions.yaml",
        ]
    ),
)

__all__ = ["powerschool_db_sync_extensions", "powerschool_db_resync_extensions"]
