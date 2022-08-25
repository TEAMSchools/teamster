from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.graphs.powerschool.db import run_queries
from teamster.core.resources.google import gcs_file_manager
from teamster.core.resources.sqlalchemy import oracle

powerschool_db_extract = run_queries.to_job(
    name="powerschool_db_extract",
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
            "./teamster/local/config/powerschool/db/resource.yaml",
        ]
    ),
)

__all__ = [
    "powerschool_db_extract",
]
