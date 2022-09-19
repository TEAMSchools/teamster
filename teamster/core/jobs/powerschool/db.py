from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.graphs.powerschool.db import bar
from teamster.core.resources.google import gcs_file_manager
from teamster.core.resources.sqlalchemy import oracle

powerschool_db_extract = bar.to_job(
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

# powerschool_db_resync = generate_queries.to_job(
#     name="powerschool_db_resync",
#     executor_def=k8s_job_executor,
#     resource_defs={
#         "db": oracle,
#         "ssh": ssh_resource,
#         "file_manager": gcs_file_manager,
#         "io_manager": gcs_pickle_io_manager,
#         "gcs": gcs_resource,
#     },
#     config=config_from_files(
#         [
#             "./teamster/core/config/google/resource.yaml",
#             "./teamster/core/config/powerschool/db/resource.yaml",
#             "./teamster/local/config/powerschool/db/query-resync.yaml",
#             "./teamster/local/config/powerschool/db/query-resync-log.yaml",
#             "./teamster/local/config/powerschool/db/query-resync-attendance.yaml",
#             "./teamster/local/config/powerschool/db/query-resync-storedgrades.yaml",
#             "./teamster/local/config/powerschool/db/query-resync-pgfinalgrades.yaml",
#             "./teamster/local/config/powerschool/db/query-resync-assignmentscore.yaml",
#         ]
#     ),
#     tags={"dagster/retry_strategy": "ALL_STEPS"},
# )

__all__ = ["powerschool_db_extract"]
