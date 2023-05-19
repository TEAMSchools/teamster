from dagster import (
    AutoMaterializePolicy,
    Definitions,
    EnvVar,
    config_from_files,
    load_assets_from_modules,
)
from dagster_dbt import dbt_cli_resource
from dagster_gcp import BigQueryResource, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.sqlalchemy.resources import (
    MSSQLResource,
    OracleResource,
    SqlAlchemyEngineResource,
)

from . import CODE_LOCATION, datagun, dbt, deanslist, iready, powerschool, renlearn

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[powerschool], group_name="powerschool"),
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[deanslist], group_name="deanslist"),
        *load_assets_from_modules(modules=[renlearn], group_name="renlearn"),
        *load_assets_from_modules(modules=[iready], group_name="iready"),
        *load_assets_from_modules(
            modules=[dbt], auto_materialize_policy=AutoMaterializePolicy.eager()
        ),
    ],
    jobs=[*datagun.jobs, *deanslist.jobs],
    schedules=[*datagun.schedules, *powerschool.schedules, *deanslist.schedules],
    sensors=[*powerschool.sensors, *renlearn.sensors, *iready.sensors],
    resources={
        "io_manager": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_pickle.yaml"])
        ),
        "gcs_fp_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_filepath.yaml"])
        ),
        "gcs_avro_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_avro.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files([f"{resource_config_dir}/gcs.yaml"])
        ),
        "warehouse": MSSQLResource(
            engine=SqlAlchemyEngineResource(
                dialect="mssql",
                driver="pyodbc",
                host="winsql05.kippnj.org",
                port=1433,
                database="gabby",
                username=EnvVar("MSSQL_USERNAME"),
                password=EnvVar("MSSQL_PASSWORD"),
            ),
            driver="ODBC Driver 18 for SQL Server",
        ),
        "bq": BigQueryResource(project="teamster-332318"),
        "sftp_pythonanywhere": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_pythonanywhere.yaml"])
        ),
        "sftp_renlearn": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_renlearn.yaml"])
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/ssh_powerschool.yaml"])
        ),
        "ps_db": OracleResource(
            engine=SqlAlchemyEngineResource(
                dialect="oracle",
                driver="cx_oracle",
                username="PSNAVIGATOR",
                host="localhost",
                database="PSPRODDB",
                port=1521,
                password=EnvVar("KIPPMIAMI_PS_DB_PASSWORD"),
            ),
            version="19.0.0.0.0",
            prefetchrows=100000,
            arraysize=100000,
        ),
        "dbt": dbt_cli_resource.configured(
            {
                "project-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
                "profiles-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
            }
        ),
        "deanslist": DeansListResource(
            subdomain="kippnj",
            api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
        ),
        "sftp_iready": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_iready.yaml"])
        ),
    },
)
