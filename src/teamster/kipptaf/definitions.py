from dagster import Definitions, EnvVar, config_from_files, load_assets_from_modules
from dagster_dbt import dbt_cli_resource
from dagster_gcp import bigquery_resource, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.alchemer.resources import alchemer_resource
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.google.resources.sheets import google_sheets
from teamster.core.schoolmint.resources import schoolmint_grow_resource
from teamster.core.sqlalchemy.resources import mssql
from teamster.core.utils.variables import LOCAL_TIME_ZONE

from . import CODE_LOCATION, alchemer, datagun, dbt, schoolmint

core_resource_config_dir = "src/teamster/core/config/resources"
local_resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[datagun.assets], group_name="datagun"),
        *load_assets_from_modules(modules=[schoolmint.assets], group_name="schoolmint"),
        *load_assets_from_modules(modules=[alchemer.assets], group_name="alchemer"),
        *load_assets_from_modules(modules=[dbt.assets]),
    ],
    jobs=[*datagun.jobs.__all__, *schoolmint.jobs.__all__],
    schedules=[*datagun.schedules.__all__, *schoolmint.schedules.__all__],
    sensors=[*dbt.sensors.__all__],
    resources={
        "dbt": dbt_cli_resource.configured(
            {
                "project-dir": f"teamster-dbt/{CODE_LOCATION}",
                "profiles-dir": f"teamster-dbt/{CODE_LOCATION}",
            }
        ),
        "bq": bigquery_resource.configured(
            config_from_files([f"{core_resource_config_dir}/gcs.yaml"])
        ),
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
        "schoolmint_grow": schoolmint_grow_resource.configured(
            config_from_files([f"{core_resource_config_dir}/schoolmint.yaml"])
        ),
        "alchemer": alchemer_resource(
            api_token=EnvVar("ALCHEMER_API_TOKEN"),
            api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
            time_zone=LOCAL_TIME_ZONE,
            **config_from_files([f"{core_resource_config_dir}/alchemer.yaml"]),
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
        "gcs_avro_io": gcs_io_manager.configured(
            config_from_files([f"{local_resource_config_dir}/io_avro.yaml"])
        ),
    },
)
