from dagster import config_from_files
from dagster_gcp.gcs import gcs_file_manager, gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor

from teamster.core.powerschool.graphs.db import sync_standard  # test_sync_table
from teamster.core.resources.sqlalchemy import oracle
from teamster.core.resources.ssh import ssh_resource

# test_powerschool_db_sync = test_sync_table.to_job(
#     name="test_powerschool_db_sync",
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
#             "./teamster/core/resources/config/google.yaml",
#             "./teamster/core/powerschool/config/db/resource.yaml",
#             "./teamster/core/powerschool/config/db/query-test.yaml",
#         ]
#     ),
# )

powerschool_db_sync_std = sync_standard.to_job(
    name="powerschool_db_sync_std",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/powerschool/config/db/resource.yaml",
            "teamster/core/powerschool/config/db/sync-standard.yaml",
            # TODO: combine local ext tables (use try/except?)
        ]
    ),
)


__all__ = [
    "powerschool_db_sync_std",
    # "test_powerschool_db_sync",
]
