from dagster import config_from_files
from dagster_gcp.gcs import gcs_pickle_io_manager, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.datagun.graphs import etl_sftp
from teamster.core.resources.google import gcs_file_manager
from teamster.core.resources.sqlalchemy import mssql
from teamster.local.datagun.graphs import powerschool_autocomm

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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-powerschool.yaml",
        ]
    ),
)

datagun_adp = etl_sftp.to_job(
    name="datagun_adp",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-adp.yaml",
        ]
    ),
)

datagun_alchemer = etl_sftp.to_job(
    name="datagun_alchemer",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-alchemer.yaml",
        ]
    ),
)

datagun_blissbook = etl_sftp.to_job(
    name="datagun_blissbook",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-blissbook.yaml",
        ]
    ),
)

datagun_coupa = etl_sftp.to_job(
    name="datagun_coupa",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-coupa.yaml",
        ]
    ),
)

datagun_egencia = etl_sftp.to_job(
    name="datagun_egencia",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-egencia.yaml",
        ]
    ),
)

datagun_fpodms = etl_sftp.to_job(
    name="datagun_fpodms",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-fpodms.yaml",
        ]
    ),
)

datagun_idauto = etl_sftp.to_job(
    name="datagun_idauto",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-idauto.yaml",
        ]
    ),
)

datagun_littlesis = etl_sftp.to_job(
    name="datagun_littlesis",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-littlesis.yaml",
        ]
    ),
)

datagun_njdoe = etl_sftp.to_job(
    name="datagun_njdoe",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-njdoe.yaml",
        ]
    ),
)

datagun_whetstone = etl_sftp.to_job(
    name="datagun_whetstone",
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
            "teamster/core/resources/config/google.yaml",
            "teamster/core/datagun/config/resource.yaml",
            "teamster/local/datagun/config/query-whetstone.yaml",
        ]
    ),
)

__all__ = [
    "datagun_ps_autocomm",
    "datagun_adp",
    "datagun_alchemer",
    "datagun_blissbook",
    "datagun_coupa",
    "datagun_egencia",
    "datagun_fpodms",
    "datagun_idauto",
    "datagun_littlesis",
    "datagun_njdoe",
    "datagun_whetstone",
]
