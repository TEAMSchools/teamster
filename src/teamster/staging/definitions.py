from dagster import Definitions, EnvVar, config_from_files, load_assets_from_modules
from dagster_dbt import dbt_cli_resource
from dagster_gcp import BigQueryResource, gcs_resource
from dagster_k8s import k8s_job_executor
from dagster_ssh import ssh_resource

from teamster.core.adp.resources import WorkforceManagerResource
from teamster.core.alchemer.resources import AlchemerResource
from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.google.resources.sheets import GoogleSheetsResource
from teamster.core.schoolmint.resources import schoolmint_grow_resource
from teamster.core.smartrecruiters.resources import SmartRecruitersResource
from teamster.core.sqlalchemy.resources import (
    MSSQLResource,
    OracleResource,
    SqlAlchemyEngineResource,
)

from . import (
    CODE_LOCATION,
    achieve3k,
    adp,
    alchemer,
    clever,
    datagun,
    dbt,
    deanslist,
    iready,
    powerschool,
    renlearn,
    schoolmint,
    smartrecruiters,
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
        *load_assets_from_modules(modules=[adp], group_name="adp"),
        *load_assets_from_modules(
            modules=[smartrecruiters], group_name="smartrecruiters"
        ),
    ],
    jobs=[
        *datagun.jobs,
        *deanslist.jobs,
        *schoolmint.jobs,
        *adp.jobs,
        *smartrecruiters.jobs,
    ],
    schedules=[
        # *datagun.schedules,
        *schoolmint.schedules,
        *adp.schedules,
        *smartrecruiters.schedules,
    ],
    sensors=[
        *achieve3k.sensors,
        *adp.sensors,
        *alchemer.sensors,
        *clever.sensors,
        *iready.sensors,
        *powerschool.sensors,
        *renlearn.sensors,
    ],
    resources={
        "io_manager": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_pickle.yaml"])
        ),
        "gcs_avro_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_avro.yaml"])
        ),
        "gcs_fp_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_filepath.yaml"])
        ),
        "gcs": gcs_resource.configured(
            config_from_files([f"{resource_config_dir}/gcs.yaml"])
        ),
        "dbt": dbt_cli_resource.configured(
            {
                "project-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
                "profiles-dir": f"/root/app/teamster-dbt/{CODE_LOCATION}",
            }
        ),
        "bq": BigQueryResource(project="teamster-332318"),
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
        "gsheets": GoogleSheetsResource(folder_id="1x3lycfK1nT4KaERu6hDmIxQbGdKaDzK5"),
        "schoolmint_grow": schoolmint_grow_resource.configured(
            config_from_files([f"{resource_config_dir}/schoolmint.yaml"])
        ),
        "alchemer": AlchemerResource(
            api_token=EnvVar("ALCHEMER_API_TOKEN"),
            api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
            api_version="v5",
        ),
        "adp_wfm": WorkforceManagerResource(
            subdomain=EnvVar("ADP_WFM_SUBDOMAIN"),
            app_key=EnvVar("ADP_WFM_APP_KEY"),
            client_id=EnvVar("ADP_WFM_CLIENT_ID"),
            client_secret=EnvVar("ADP_WFM_CLIENT_SECRET"),
            username=EnvVar("ADP_WFM_USERNAME"),
            password=EnvVar("ADP_WFM_PASSWORD"),
        ),
        "smartrecruiters": SmartRecruitersResource(
            smart_token=EnvVar("SMARTRECRUITERS_SMARTTOKEN")
        ),
        "ps_db": OracleResource(
            engine=SqlAlchemyEngineResource(
                dialect="oracle",
                driver="cx_oracle",
                username="PSNAVIGATOR",
                host="localhost",
                database="PSPRODDB",
                port=1521,
                password=EnvVar("STAGING_PS_DB_PASSWORD"),
            ),
            version="19.0.0.0.0",
            prefetchrows=100000,
            arraysize=100000,
        ),
        "ps_ssh": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/ssh_powerschool.yaml"])
        ),
        "deanslist": DeansListResource(
            subdomain="kippnj",
            api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
        ),
        "sftp_achieve3k": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_achieve3k.yaml"])
        ),
        "sftp_adp": ssh_resource.configured(
            config_from_files([f"{resource_config_dir}/sftp_adp.yaml"])
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
