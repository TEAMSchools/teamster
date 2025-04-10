import os

from dagster import EnvVar
from dagster_dbt import DbtCliResource
from dagster_gcp import BigQueryResource, GCSResource
from dagster_shared import check
from dagster_slack import SlackResource

from teamster import GCS_PROJECT_NAME
from teamster.core.io_managers.gcs import GCSIOManager
from teamster.libraries.deanslist.resources import DeansListResource
from teamster.libraries.overgrad.resources import OvergradResource
from teamster.libraries.powerschool.sis.resources import PowerSchoolODBCResource
from teamster.libraries.ssh.resources import SSHResource

GCS_RESOURCE = GCSResource(project=GCS_PROJECT_NAME)


def get_io_manager_gcs_pickle(code_location):
    if os.getenv("DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT") == "1":
        code_location = "test"

    return GCSIOManager(
        gcs=GCS_RESOURCE, gcs_bucket=f"teamster-{code_location}", object_type="pickle"
    )


def get_io_manager_gcs_avro(code_location, test=False):
    if os.getenv("DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT") == "1":
        code_location = "test"
        test = True

    return GCSIOManager(
        gcs=GCS_RESOURCE,
        gcs_bucket=f"teamster-{code_location}",
        object_type="avro",
        test=test,
    )


def get_io_manager_gcs_file(code_location, test=False):
    if os.getenv("DAGSTER_CLOUD_IS_BRANCH_DEPLOYMENT") == "1":
        code_location = "test"
        test = True

    return GCSIOManager(
        gcs=GCS_RESOURCE,
        gcs_bucket=f"teamster-{code_location}",
        object_type="file",
        test=test,
    )


def get_dbt_cli_resource(dbt_project, test=False):
    if test:
        return DbtCliResource(
            project_dir=dbt_project, dbt_executable="/workspaces/teamster/.venv/bin/dbt"
        )
    else:
        return DbtCliResource(project_dir=dbt_project)


def get_powerschool_ssh_resource():
    return SSHResource(
        remote_host=EnvVar("PS_SSH_HOST"),
        remote_port=int(check.not_none(value=EnvVar("PS_SSH_PORT").get_value())),
        username=EnvVar("PS_SSH_USERNAME"),
        tunnel_remote_host=EnvVar("PS_SSH_REMOTE_BIND_HOST"),
    )


BIGQUERY_RESOURCE = BigQueryResource(project=GCS_PROJECT_NAME)

DB_POWERSCHOOL = PowerSchoolODBCResource(
    user=EnvVar("PS_DB_USERNAME"),
    password=EnvVar("PS_DB_PASSWORD"),
    host=EnvVar("PS_DB_HOST"),
    port=EnvVar("PS_DB_PORT"),
    service_name=EnvVar("PS_DB_DATABASE"),
)

DEANSLIST_RESOURCE = DeansListResource(
    subdomain=EnvVar("DEANSLIST_SUBDOMAIN"),
    api_key_map="/etc/secret-volume/deanslist_api_key_map_yaml",
)

OVERGRAD_RESOURCE = OvergradResource(api_key=EnvVar("OVERGRAD_API_KEY"), page_limit=100)

SLACK_RESOURCE = SlackResource(token=EnvVar("SLACK_TOKEN"))

SSH_COUCHDROP = SSHResource(
    remote_host=EnvVar("COUCHDROP_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("COUCHDROP_SFTP_USERNAME"),
    password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
)

SSH_EDPLAN = SSHResource(
    remote_host=EnvVar("EDPLAN_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("EDPLAN_SFTP_USERNAME"),
    password=EnvVar("EDPLAN_SFTP_PASSWORD"),
)

SSH_IREADY = SSHResource(
    remote_host=EnvVar("IREADY_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("IREADY_SFTP_USERNAME"),
    password=EnvVar("IREADY_SFTP_PASSWORD"),
)

SSH_RENLEARN = SSHResource(
    remote_host=EnvVar("RENLEARN_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("RENLEARN_SFTP_USERNAME"),
    password=EnvVar("RENLEARN_SFTP_PASSWORD"),
)

SSH_TITAN = SSHResource(
    remote_host=EnvVar("TITAN_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("TITAN_SFTP_USERNAME"),
    password=EnvVar("TITAN_SFTP_PASSWORD"),
)
