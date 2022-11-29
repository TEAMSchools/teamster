from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.resources.google import gcs_file_manager
from teamster.core.resources.sqlalchemy import mssql
from teamster.local.datagun.graphs import cpn, powerschool_autocomm

datagun_ps_autocomm = powerschool_autocomm.to_job(
    name="datagun_ps_autocomm",
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
            "src/teamster/core/resources/config/google.yaml",
            "src/teamster/core/datagun/config/resource.yaml",
            "src/teamster/local/datagun/config/query-powerschool.yaml",
        ]
    ),
)

datagun_cpn = cpn.to_job(
    name="datagun_cpn",
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
            "src/teamster/core/resources/config/google.yaml",
            "src/teamster/core/datagun/config/resource.yaml",
            "src/teamster/local/datagun/config/query-cpn.yaml",
        ]
    ),
)

__all__ = ["datagun_ps_autocomm", "datagun_cpn"]
