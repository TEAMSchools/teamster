from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.datagun.graphs import test_etl_gsheet, test_etl_sftp
from teamster.core.resources.google import gcs_file_manager, google_sheets
from teamster.core.resources.sqlalchemy import mssql

datagun_etl_sftp = test_etl_sftp.to_job(
    name="datagun_etl_sftp",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": mssql,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
        "sftp": ssh_resource,
    },
    config=config_from_files(
        [
            "./teamster/core/resources/config/google.yaml",
            "./teamster/core/datagun/config/resource.yaml",
            "./teamster/core/datagun/config/query-sftp-test.yaml",
        ]
    ),
)

datagun_etl_gsheets = test_etl_gsheet.to_job(
    name="datagun_etl_gsheets",
    executor_def=k8s_job_executor,
    resource_defs={
        "db": mssql,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
        "gsheet": google_sheets,
    },
    config=config_from_files(
        [
            "./teamster/core/resources/config/google.yaml",
            "./teamster/core/datagun/config/resource.yaml",
            "./teamster/core/datagun/config/query-gsheets-test.yaml",
        ]
    ),
)

__all__ = ["datagun_etl_sftp", "datagun_etl_gsheets"]
