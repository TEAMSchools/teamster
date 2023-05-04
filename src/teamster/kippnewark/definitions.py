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

from teamster.core.deanslist.resources import deanslist_resource
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.sqlalchemy.resources import mssql, oracle

from . import CODE_LOCATION, datagun, dbt, deanslist, powerschool

core_resource_config_dir = "src/teamster/core/config/resources"
local_resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[powerschool], group_name="powerschool"),
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[deanslist], group_name="deanslist"),
        *load_assets_from_modules(
            modules=[dbt], auto_materialize_policy=AutoMaterializePolicy.eager()
        ),
    ],
    jobs=[*datagun.jobs, *deanslist.jobs],
    schedules=[*datagun.schedules, *powerschool.schedules, *deanslist.schedules],
    sensors=[*powerschool.sensors],
    resources={
        "warehouse": mssql.configured(
            config_from_files([f"{core_resource_config_dir}/warehouse.yaml"])
        ),
        "bq": bigquery_resource.configured(
            config_from_files([f"{core_resource_config_dir}/gcs.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files([f"{core_resource_config_dir}/gcs.yaml"])
        ),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files([f"{core_resource_config_dir}/sftp_pythonanywhere.yaml"])
        ),
        "ps_db": oracle.configured(
            config_from_files(
                [
                    f"{core_resource_config_dir}/db_powerschool.yaml",
                    f"{local_resource_config_dir}/db_powerschool.yaml",
                ]
            )
        ),
        "io_manager": gcs_io_manager.configured(
            config_from_files([f"{local_resource_config_dir}/io_pickle.yaml"])
        ),
        "dbt": dbt_cli_resource.configured(
            {
                "project-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
                "profiles-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
            }
        ),
        "sftp_nps": ssh_resource.configured(
            config_from_files([f"{local_resource_config_dir}/sftp_nps.yaml"])
        ),
        "deanslist": deanslist_resource.configured(
            config_from_files([f"{core_resource_config_dir}/deanslist.yaml"])
        ),
        "gcs_fp_io": gcs_io_manager.configured(
            config_from_files([f"{local_resource_config_dir}/io_filepath.yaml"])
        ),
        "gcs_avro_io": gcs_io_manager.configured(
            config_from_files([f"{local_resource_config_dir}/io_avro.yaml"])
        ),
    },
)
