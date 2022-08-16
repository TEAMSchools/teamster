from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager
from dagster_gcp.gcs.resources import gcs_resource
from dagster_ssh import ssh_resource

from teamster.core.graphs.datagun import run_queries
from teamster.core.resources.db import mssql
from teamster.core.resources.google import gcs_file_manager, google_sheets

datagun_etl_sftp = run_queries.to_job(
    name="datagun_etl_sftp",
    resource_defs={
        "db": mssql,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
        "destination": ssh_resource,
    },
    config=config_from_files(
        [
            "./teamster/core/config/datagun/resource.yaml",
            "./teamster/core/config/google/resource.yaml",
            "./teamster/kippnewark/config/datagun/template-query-sftp.yaml",
        ]
    ),
)

datagun_etl_gsheets = run_queries.to_job(
    name="datagun_etl_gsheets",
    resource_defs={
        "db": mssql,
        "file_manager": gcs_file_manager,
        "io_manager": gcs_pickle_io_manager,
        "gcs": gcs_resource,
        "destination": google_sheets,
    },
    config=config_from_files(
        [
            "./teamster/core/config/datagun/resource.yaml",
            "./teamster/core/config/google/resource.yaml",
            "./teamster/kippnewark/config/datagun/template-query-gsheets.yaml",
        ]
    ),
)

__all__ = ["datagun_etl_sftp", "datagun_etl_gsheets"]
