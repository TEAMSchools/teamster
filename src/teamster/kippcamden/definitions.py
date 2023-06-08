from dagster import (
    AutoMaterializePolicy,
    Definitions,
    EnvVar,
    config_from_files,
    load_assets_from_modules,
)
from dagster_dbt import DbtCliClientResource
from dagster_gcp import BigQueryResource
from dagster_gcp.gcs import ConfigurablePickledObjectGCSIOManager, GCSResource
from dagster_k8s import k8s_job_executor

from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.resources.io import gcs_io_manager
from teamster.core.sqlalchemy.resources import (
    MSSQLResource,
    OracleResource,
    SqlAlchemyEngineResource,
)
from teamster.core.ssh.resources import SSHConfigurableResource

from . import (
    CODE_LOCATION,
    GCS_PROJECT_NAME,
    datagun,
    dbt,
    deanslist,
    edplan,
    powerschool,
    titan,
)

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[powerschool], group_name="powerschool"),
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[deanslist], group_name="deanslist"),
        *load_assets_from_modules(modules=[edplan], group_name="edplan"),
        *load_assets_from_modules(modules=[titan], group_name="titan"),
        *load_assets_from_modules(
            modules=[dbt], auto_materialize_policy=AutoMaterializePolicy.eager()
        ),
    ],
    jobs=[*datagun.jobs, *deanslist.jobs],
    schedules=[*datagun.schedules, *powerschool.schedules, *deanslist.schedules],
    sensors=[*powerschool.sensors, *edplan.sensors, *titan.sensors],
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
        "gcs": GCSResource(project="teamster-332318"),
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
                password=EnvVar("KIPPCAMDEN_PS_DB_PASSWORD"),
            ),
            version="19.0.0.0.0",
            prefetchrows=100000,
            arraysize=100000,
        ),
        "deanslist": DeansListResource(
            subdomain="kippnj",
            api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
        ),
        "ssh_cpn": SSHConfigurableResource(
            remote_host="sftp.careevolution.com",
            username=EnvVar("CPN_SFTP_USERNAME"),
            password=EnvVar("CPN_SFTP_PASSWORD"),
        ),
        "ssh_edplan": SSHConfigurableResource(
            remote_host="secureftp.easyiep.com",
            username=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_USERNAME"),
            password=EnvVar("KIPPCAMDEN_EDPLAN_SFTP_PASSWORD"),
        ),
        "ssh_powerschool": SSHConfigurableResource(
            remote_host="pskcna.kippnj.org",
            remote_port=EnvVar("KIPPCAMDEN_PS_SSH_PORT"),
            username=EnvVar("KIPPCAMDEN_PS_SSH_USERNAME"),
            password=EnvVar("KIPPCAMDEN_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("KIPPCAMDEN_PS_SSH_REMOTE_BIND_HOST"),
        ),
        "ssh_pythonanywhere": SSHConfigurableResource(
            remote_host="ssh.pythonanywhere.com",
            username=EnvVar("PYTHONANYWHERE_SFTP_USERNAME"),
            password=EnvVar("PYTHONANYWHERE_SFTP_PASSWORD"),
        ),
        "ssh_titan": SSHConfigurableResource(
            remote_host="sftp.titank12.com",
            username=EnvVar("KIPPCAMDEN_TITAN_SFTP_USERNAME"),
            password=EnvVar("KIPPCAMDEN_TITAN_SFTP_PASSWORD"),
        ),
    },
)
