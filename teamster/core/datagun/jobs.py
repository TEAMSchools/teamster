from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.datagun.graphs import test_etl
from teamster.core.resources.google import gcs_file_manager, google_sheets
from teamster.core.resources.sqlalchemy import mssql

test_datagun_etl = test_etl.to_job(
    name="datagun_etl",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": mssql,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
        "sftp": ssh_resource,
        "gsheet": google_sheets,
    },
    config=config_from_files(
        [
            "./teamster/core/resources/config/google.yaml",
            "./teamster/core/datagun/config/resource.yaml",
            "./teamster/core/datagun/config/query-test.yaml",
        ]
    ),
)

__all__ = ["test_datagun_etl"]
