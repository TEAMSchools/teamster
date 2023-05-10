from dagster import Definitions, config_from_files, load_assets_from_modules
from dagster_dbt import dbt_cli_resource
from dagster_gcp import bigquery_resource, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.alchemer.resources import alchemer_resource
from teamster.core.deanslist.resources import deanslist_resource
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.google.resources.sheets import google_sheets
from teamster.core.schoolmint.resources import schoolmint_grow_resource
from teamster.core.sqlalchemy.resources import mssql, oracle

from . import (
    CODE_LOCATION,
    achieve3k,
    alchemer,
    clever,
    datagun,
    dbt,
    deanslist,
    iready,
    powerschool,
    renlearn,
    schoolmint,
)

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[achieve3k], group_name="achieve3k"),
        *load_assets_from_modules(modules=[alchemer], group_name="alchemer"),
        *load_assets_from_modules(modules=[clever], group_name="clever"),
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[dbt]),
        *load_assets_from_modules(modules=[deanslist], group_name="deanslist"),
        *load_assets_from_modules(modules=[iready], group_name="iready"),
        *load_assets_from_modules(modules=[powerschool], group_name="powerschool"),
        *load_assets_from_modules(modules=[renlearn], group_name="renlearn"),
        *load_assets_from_modules(modules=[schoolmint], group_name="schoolmint"),
    ],
    jobs=[*datagun.jobs, *deanslist.jobs],
    sensors=[
        *achieve3k.sensors,
        *alchemer.sensors,
        *clever.sensors,
        *iready.sensors,
        *powerschool.sensors,
        *renlearn.sensors,
    ],
    resources={
        "gcs": gcs_resource.configured(
            config_from_files([f"{resource_config_dir}/gcs.yaml"])
        ),
        "io_manager": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_pickle.yaml"])
        ),
        "gcs_fp_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_filepath.yaml"])
        ),
        "gcs_avro_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_avro.yaml"])
        ),
        "gsheets": google_sheets.configured(
            config_from_files([f"{resource_config_dir}/gsheets.yaml"])
        ),
        "bq": bigquery_resource.configured(
            config_from_files([f"{resource_config_dir}/gcs.yaml"])
        ),
        "warehouse": mssql.configured(
            config_from_files([f"{resource_config_dir}/warehouse.yaml"])
        ),
        "dbt": dbt_cli_resource.configured(
            {
                "project-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
                "profiles-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
            }
        ),
        "ps_db": oracle.configured(
            config_from_files([f"{resource_config_dir}/db_powerschool.yaml"])
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/ssh_powerschool.yaml"])
        ),
        "deanslist": deanslist_resource.configured(
            config_from_files([f"{resource_config_dir}/deanslist.yaml"])
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
        "sftp_clever": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_clever.yaml"])
        ),
        "sftp_clever_reports": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_clever_reports.yaml"])
        ),
        "sftp_iready": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_iready.yaml"])
        ),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_pythonanywhere.yaml"])
        ),
        "sftp_renlearn": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_renlearn.yaml"])
        ),
        "sftp_staging": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_pythonanywhere.yaml"])
        ),
    },
)
