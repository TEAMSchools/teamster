from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_gcp.gcs import gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.google.resources.sheets import google_sheets
from teamster.core.sqlalchemy.resources import mssql

from . import CODE_LOCATION, datagun

core_resource_config_dir = "src/teamster/core/config/resources"
local_resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(modules=[datagun.assets], group_name="datagun"),
    jobs=datagun.jobs.__all__,
    schedules=datagun.schedules.__all__,
    resources={
        "gcs": gcs_resource.configured(
            config_from_files([f"{core_resource_config_dir}/gcs.yaml"])
        ),
        "warehouse": mssql.configured(
            config_from_files([f"{core_resource_config_dir}/warehouse.yaml"])
        ),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files([f"{core_resource_config_dir}/sftp_pythonanywhere.yaml"])
        ),
        "io_manager": gcs_io_manager.configured(
            config_from_files([f"{local_resource_config_dir}/io_pickle.yaml"])
        ),
        "gsheets": google_sheets.configured(
            config_from_files([f"{core_resource_config_dir}/gsheets.yaml"])
        ),
        "sftp_blissbook": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_blissbook.yaml"])
        ),
        "sftp_clever": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_clever.yaml"])
        ),
        "sftp_coupa": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_coupa.yaml"])
        ),
        "sftp_deanslist": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_deanslist.yaml"])
        ),
        "sftp_egencia": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_egencia.yaml"])
        ),
        "sftp_illuminate": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_illuminate.yaml"])
        ),
        "sftp_kipptaf": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_kipptaf.yaml"])
        ),
        "sftp_littlesis": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_littlesis.yaml"])
        ),
        "sftp_razkids": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_razkids.yaml"])
        ),
        "sftp_read180": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_read180.yaml"])
        ),
    },
)
