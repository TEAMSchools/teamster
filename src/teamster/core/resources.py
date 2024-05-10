from dagster import EnvVar
from dagster_dbt import DbtCliResource
from dagster_gcp import BigQueryResource, GCSResource

from teamster import GCS_PROJECT_NAME
from teamster.core.deanslist.resources import DeansListResource
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.sqlalchemy.resources import OracleResource, SqlAlchemyEngineResource
from teamster.core.ssh.resources import SSHResource

GCS_RESOURCE = GCSResource(project=GCS_PROJECT_NAME)

BIGQUERY_RESOURCE = BigQueryResource(project=GCS_PROJECT_NAME)

DB_POWERSCHOOL = OracleResource(
    engine=SqlAlchemyEngineResource(
        dialect="oracle",
        driver="oracledb",
        host=EnvVar("PS_DB_HOST"),
        database=EnvVar("PS_DB_DATABASE"),
        port=int(EnvVar("PS_DB_PORT").get_value()),  # type: ignore
        username=EnvVar("PS_DB_USERNAME"),
        password=EnvVar("PS_DB_PASSWORD"),
    ),
    version=EnvVar("PS_DB_VERSION"),
    prefetchrows=100000,
    arraysize=100000,
)

DEANSLIST_RESOURCE = DeansListResource(
    subdomain=EnvVar("DEANSLIST_SUBDOMAIN"),
    api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
)

SSH_COUCHDROP = SSHResource(
    remote_host=EnvVar("COUCHDROP_SFTP_HOST"),
    username=EnvVar("COUCHDROP_SFTP_USERNAME"),
    password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
)

SSH_EDPLAN = SSHResource(
    remote_host=EnvVar("EDPLAN_SFTP_HOST"),
    username=EnvVar("EDPLAN_SFTP_USERNAME"),
    password=EnvVar("EDPLAN_SFTP_PASSWORD"),
)

SSH_IREADY = SSHResource(
    remote_host=EnvVar("IREADY_SFTP_HOST"),
    username=EnvVar("IREADY_SFTP_USERNAME"),
    password=EnvVar("IREADY_SFTP_PASSWORD"),
)

SSH_RENLEARN = SSHResource(
    remote_host=EnvVar("RENLEARN_SFTP_HOST"),
    username=EnvVar("RENLEARN_SFTP_USERNAME"),
    password=EnvVar("RENLEARN_SFTP_PASSWORD"),
)

SSH_TITAN = SSHResource(
    remote_host=EnvVar("TITAN_SFTP_HOST"),
    username=EnvVar("TITAN_SFTP_USERNAME"),
    password=EnvVar("TITAN_SFTP_PASSWORD"),
)


def get_io_manager_gcs_pickle(code_location):
    return GCSIOManager(
        gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{code_location}", object_type="pickle"
    )


def get_io_manager_gcs_avro(code_location):
    return GCSIOManager(
        gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{code_location}", object_type="avro"
    )


def get_io_manager_gcs_file(code_location):
    return GCSIOManager(
        gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{code_location}", object_type="file"
    )


def get_dbt_cli_resource(code_location):
    return DbtCliResource(project_dir=f"src/dbt/{code_location}")


def get_ssh_resource_powerschool(remote_host):
    return SSHResource(
        remote_host=remote_host,
        remote_port=int(EnvVar("PS_SSH_PORT").get_value()),  # type: ignore
        username=EnvVar("PS_SSH_USERNAME"),
        password=EnvVar("PS_SSH_PASSWORD"),
        tunnel_remote_host=EnvVar("PS_SSH_REMOTE_BIND_HOST"),
    )
