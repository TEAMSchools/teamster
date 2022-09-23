from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.graphs.powerschool.db import sync_all, test_sync_all
from teamster.core.resources.google import gcs_file_manager
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource

test_powerschool_db_sync = test_sync_all.to_job(
    name="test_powerschool_db_sync",
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
            "./teamster/core/config/google/resource.yaml",
            "./teamster/core/config/powerschool/db/resource.yaml",
            "./teamster/core/config/powerschool/db/query-test.yaml",
        ]
    ),
)

powerschool_db_sync_standard = sync_all.to_job(
    name="powerschool_db_sync_standard",
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
            "./teamster/core/config/google/resource.yaml",
            "./teamster/core/config/powerschool/db/resource.yaml",
            "./teamster/core/config/powerschool/db/query-standard.yaml",
        ]
    ),
)

__all__ = ["powerschool_db_sync_standard", "test_powerschool_db_sync"]
