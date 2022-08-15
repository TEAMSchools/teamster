from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.common.graphs.powerschool.db import run_queries
from teamster.common.resources.db import oracle
from teamster.common.resources.google import gcs_file_manager

powerschool_db_extract = run_queries.to_job(
    name="powerschool_extract",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": oracle,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
    },
    config=config_from_files(
        [
            "./teamster/common/config/powerschool/db/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/kippcamden/config/powerschool/db/query-default.yaml",
        ]
    ),
)

__all__ = [
    "powerschool_db_extract",
]
