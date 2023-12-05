from dagster import Definitions, EnvVar, load_assets_from_modules
from dagster_dbt import DbtCliResource
from dagster_gcp import BigQueryResource, GCSResource
from dagster_k8s import k8s_job_executor

from teamster import GCS_PROJECT_NAME
from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHResource
from teamster.kippmiami import (
    CODE_LOCATION,
    datagun,
    dbt,
    deanslist,
    fldoe,
    iready,
    powerschool,
    renlearn,
)

GCS_RESOURCE = GCSResource(project=GCS_PROJECT_NAME)

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[datagun, dbt, deanslist, fldoe, renlearn, iready, powerschool]
    ),
    jobs=[*datagun.jobs, *deanslist.jobs],
    schedules=[
        *datagun.schedules,
        *dbt.schedules,
        *powerschool.schedules,
        *deanslist.schedules,
    ],
    sensors=[*powerschool.sensors, *renlearn.sensors, *iready.sensors],
    resources={
        "gcs": GCS_RESOURCE,
        "io_manager": GCSIOManager(
            gcs=GCS_RESOURCE,
            gcs_bucket=f"teamster-{CODE_LOCATION}",
            object_type="pickle",
        ),
        "io_manager_gcs_avro": GCSIOManager(
            gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{CODE_LOCATION}", object_type="avro"
        ),
        "io_manager_gcs_file": GCSIOManager(
            gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{CODE_LOCATION}", object_type="file"
        ),
        "dbt_cli": DbtCliResource(project_dir=f"src/dbt/{CODE_LOCATION}"),
        "db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME),
        "db_powerschool": OracleResource(
            engine=SqlAlchemyEngineResource(
                dialect="oracle",
                driver="oracledb",
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
        "deanslist": DeansListResource(
            subdomain="kippnj",
            api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
        ),
        "ssh_couchdrop": SSHResource(
            remote_host="kipptaf.couchdrop.io",
            username=EnvVar("COUCHDROP_SFTP_USERNAME"),
            password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
        ),
        "ssh_iready": SSHResource(
            remote_host="prod-sftp-1.aws.cainc.com",
            username=EnvVar("IREADY_SFTP_USERNAME"),
            password=EnvVar("IREADY_SFTP_PASSWORD"),
        ),
        "ssh_powerschool": SSHResource(
            remote_host="ps.kippmiami.org",
            remote_port=EnvVar("KIPPMIAMI_PS_SSH_PORT").get_value(),
            username=EnvVar("KIPPMIAMI_PS_SSH_USERNAME"),
            password=EnvVar("KIPPMIAMI_PS_SSH_PASSWORD"),
            tunnel_remote_host=EnvVar("KIPPMIAMI_PS_SSH_REMOTE_BIND_HOST"),
        ),
        "ssh_pythonanywhere": SSHResource(
            remote_host="ssh.pythonanywhere.com",
            username=EnvVar("PYTHONANYWHERE_SFTP_USERNAME"),
            password=EnvVar("PYTHONANYWHERE_SFTP_PASSWORD"),
        ),
        "ssh_renlearn": SSHResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
        ),
    },
)
