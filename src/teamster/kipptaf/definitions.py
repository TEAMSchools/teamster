from dagster import (
    AutoMaterializePolicy,
    Definitions,
    config_from_files,
    load_assets_from_modules,
)
from dagster_dbt import dbt_cli_resource
from dagster_gcp import bigquery_resource, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.alchemer.resources import alchemer_resource
from teamster.core.dagster.sensors import run_execution_interrupted_sensor
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.google.resources.sheets import google_sheets
from teamster.core.schoolmint.resources import schoolmint_grow_resource
from teamster.core.sqlalchemy.resources import mssql

from . import (
    CODE_LOCATION,
    achieve3k,
    alchemer,
    clever,
    datagun,
    dbt,
    iready,
    renlearn,
    schoolmint,
)

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[schoolmint], group_name="schoolmint"),
        *load_assets_from_modules(modules=[alchemer], group_name="alchemer"),
        *load_assets_from_modules(modules=[renlearn], group_name="renlearn"),
        *load_assets_from_modules(modules=[clever], group_name="clever"),
        *load_assets_from_modules(modules=[achieve3k], group_name="achieve3k"),
        *load_assets_from_modules(modules=[iready], group_name="iready"),
        *load_assets_from_modules(
            modules=[dbt], auto_materialize_policy=AutoMaterializePolicy.eager()
        ),
    ],
    jobs=[*datagun.jobs, *schoolmint.jobs],
    schedules=[*datagun.schedules, *schoolmint.schedules],
    sensors=[
        *alchemer.sensors,
        *clever.sensors,
        *renlearn.sensors,
        *achieve3k.sensors,
        *iready.sensors,
        run_execution_interrupted_sensor,
    ],
    resources={
        "dbt": dbt_cli_resource.configured(
            {
                "project-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
                "profiles-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
            }
        ),
        "bq": bigquery_resource.configured(
            config_from_files([f"{resource_config_dir}/gcs.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files([f"{resource_config_dir}/gcs.yaml"])
        ),
        "warehouse": mssql.configured(
            config_from_files([f"{resource_config_dir}/warehouse.yaml"])
        ),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_pythonanywhere.yaml"])
        ),
        "io_manager": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_pickle.yaml"])
        ),
        "gsheets": google_sheets.configured(
            config_from_files([f"{resource_config_dir}/gsheets.yaml"])
        ),
        "schoolmint_grow": schoolmint_grow_resource.configured(
            config_from_files([f"{resource_config_dir}/schoolmint.yaml"])
        ),
        "alchemer": alchemer_resource.configured(
            config_from_files([f"{resource_config_dir}/alchemer.yaml"])
        ),
        "sftp_achieve3k": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_achieve3k.yaml"])
        ),
        "sftp_blissbook": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_blissbook.yaml"])
        ),
        "sftp_clever": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_clever.yaml"])
        ),
        "sftp_clever_reports": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_clever_reports.yaml"])
        ),
        "sftp_coupa": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_coupa.yaml"])
        ),
        "sftp_deanslist": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_deanslist.yaml"])
        ),
        "sftp_egencia": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_egencia.yaml"])
        ),
        "sftp_illuminate": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_illuminate.yaml"])
        ),
        "sftp_iready": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_iready.yaml"])
        ),
        "sftp_kipptaf": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_kipptaf.yaml"])
        ),
        "sftp_littlesis": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_littlesis.yaml"])
        ),
        "sftp_razkids": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_razkids.yaml"])
        ),
        "sftp_read180": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_read180.yaml"])
        ),
        "sftp_renlearn": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_renlearn.yaml"])
        ),
        "gcs_avro_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_avro.yaml"])
        ),
    },
)
