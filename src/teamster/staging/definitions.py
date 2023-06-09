from dagster import Definitions, EnvVar, config_from_files, load_assets_from_modules
from dagster_dbt import DbtCliClientResource
from dagster_gcp import BigQueryResource
from dagster_gcp.gcs import ConfigurablePickledObjectGCSIOManager, GCSResource
from dagster_k8s import k8s_job_executor

from teamster.core.adp.resources import WorkforceManagerResource
from teamster.core.alchemer.resources import AlchemerResource
from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.google.resources.sheets import GoogleSheetsResource
from teamster.core.schoolmint.resources import SchoolMintGrowResource
from teamster.core.smartrecruiters.resources import SmartRecruitersResource
from teamster.core.sqlalchemy.resources import (
    MSSQLResource,
    OracleResource,
    SqlAlchemyEngineResource,
)
from teamster.core.ssh.resources import SSHConfigurableResource

from . import (  # achieve3k,; iready,; renlearn,
    CODE_LOCATION,
    GCS_PROJECT_NAME,
    adp,
    alchemer,
    clever,
    datagun,
    dbt,
    deanslist,
    powerschool,
    schoolmint,
    smartrecruiters,
)

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[adp], group_name="adp"),
        *load_assets_from_modules(modules=[alchemer], group_name="alchemer"),
        *load_assets_from_modules(modules=[clever], group_name="clever"),
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[dbt]),
        *load_assets_from_modules(modules=[deanslist], group_name="deanslist"),
        *load_assets_from_modules(modules=[powerschool], group_name="powerschool"),
        *load_assets_from_modules(modules=[schoolmint], group_name="schoolmint"),
        *load_assets_from_modules(
            modules=[smartrecruiters], group_name="smartrecruiters"
        ),
        # *load_assets_from_modules(modules=[achieve3k], group_name="achieve3k"),
        # *load_assets_from_modules(modules=[iready], group_name="iready"),
        # *load_assets_from_modules(modules=[renlearn], group_name="renlearn"),
    ],
    jobs=[
        *datagun.jobs,
        *deanslist.jobs,
        *schoolmint.jobs,
        *adp.jobs,
        *smartrecruiters.jobs,
    ],
    # schedules=[
    #     *datagun.schedules,
    #     *schoolmint.schedules,
    #     *adp.schedules,
    #     *smartrecruiters.schedules,
    # ],
    # sensors=[
    #     *achieve3k.sensors,
    #     *adp.sensors,
    #     *alchemer.sensors,
    #     *clever.sensors,
    #     *iready.sensors,
    #     *powerschool.sensors,
    #     *renlearn.sensors,
    # ],
    resources={
        "io_manager": ConfigurablePickledObjectGCSIOManager(
            gcs=GCSResource(project=GCS_PROJECT_NAME), gcs_bucket="teamster-staging"
        ),
        "gcs_avro_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_avro.yaml"])
        ),
        "gcs_fp_io": gcs_io_manager.configured(
            config_from_files([f"{resource_config_dir}/io_filepath.yaml"])
        ),
        "gcs": GCSResource(project=GCS_PROJECT_NAME),
        "dbt": DbtCliClientResource(
            project_dir=f"/root/app/teamster-dbt/{CODE_LOCATION}",
            profiles_dir=f"/root/app/teamster-dbt/{CODE_LOCATION}",
        ),
        "db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME),
        "db_mssql": MSSQLResource(
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
        "db_powerschool": OracleResource(
            engine=SqlAlchemyEngineResource(
                dialect="oracle",
                driver="oracledb",
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
        "adp_wfm": WorkforceManagerResource(
            subdomain=EnvVar("ADP_WFM_SUBDOMAIN"),
            app_key=EnvVar("ADP_WFM_APP_KEY"),
            client_id=EnvVar("ADP_WFM_CLIENT_ID"),
            client_secret=EnvVar("ADP_WFM_CLIENT_SECRET"),
            username=EnvVar("ADP_WFM_USERNAME"),
            password=EnvVar("ADP_WFM_PASSWORD"),
        ),
        "alchemer": AlchemerResource(
            api_token=EnvVar("ALCHEMER_API_TOKEN"),
            api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
            api_version="v5",
        ),
        "deanslist": DeansListResource(
            subdomain="kippnj",
            api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
        ),
        "gsheets": GoogleSheetsResource(
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
        ),
        "schoolmint_grow": SchoolMintGrowResource(
            client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
            client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
            district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
            api_response_limit=3200,
        ),
        "smartrecruiters": SmartRecruitersResource(
            smart_token=EnvVar("SMARTRECRUITERS_SMARTTOKEN")
        ),
        "ssh_powerschool": SSHConfigurableResource(
            remote_host="teamacademy.clgpstest.com",
            remote_port=EnvVar("STAGING_PS_SSH_PORT"),
            username=EnvVar("STAGING_PS_SSH_USERNAME"),
            password=EnvVar("STAGING_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("STAGING_PS_SSH_REMOTE_BIND_HOST"),
        ),
        "ssh_pythonanywhere": SSHConfigurableResource(
            remote_host="ssh.pythonanywhere.com",
            username=EnvVar("PYTHONANYWHERE_SFTP_USERNAME"),
            password=EnvVar("PYTHONANYWHERE_SFTP_PASSWORD"),
        ),
        # "ssh_achieve3k": SSHConfigurableResource(
        #     remote_host="xfer.achieve3000.com",
        #     username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
        #     password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
        # ),
        # "ssh_adp": SSHConfigurableResource(
        #     remote_host="sftp.kippnj.org",
        #     username=EnvVar("ADP_SFTP_USERNAME"),
        #     password=EnvVar("ADP_SFTP_PASSWORD"),
        # ),
        # "ssh_clever": SSHConfigurableResource(
        #     remote_host="sftp.clever.com",
        #     username=EnvVar("CLEVER_SFTP_USERNAME"),
        #     password=EnvVar("CLEVER_SFTP_PASSWORD"),
        # ),
        # "ssh_clever_reports": SSHConfigurableResource(
        #     remote_host="reports-sftp.clever.com",
        #     username=EnvVar("CLEVER_REPORTS_SFTP_USERNAME"),
        #     password=EnvVar("CLEVER_REPORTS_SFTP_PASSWORD"),
        # ),
        # "ssh_iready": SSHConfigurableResource(
        #     remote_host="prod-sftp-1.aws.cainc.com",
        #     username=EnvVar("IREADY_SFTP_USERNAME"),
        #     password=EnvVar("IREADY_SFTP_PASSWORD"),
        # ),
        # "ssh_kipptaf": SSHConfigurableResource(
        #     remote_host="sftp.kippnj.org",
        #     username=EnvVar("KTAF_SFTP_USERNAME"),
        #     password=EnvVar("KTAF_SFTP_PASSWORD"),
        # ),
        # "ssh_renlearn": SSHConfigurableResource(
        #     remote_host="sftp.renaissance.com",
        #     username=EnvVar("KIPPNJ_RENLEARN_SFTP_USERNAME"),
        #     password=EnvVar("KIPPNJ_RENLEARN_SFTP_PASSWORD"),
        # ),
    },
)
