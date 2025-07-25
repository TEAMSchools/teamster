from dagster import EnvVar
from dagster_airbyte import AirbyteCloudWorkspace
from dagster_shared import check

from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource
from teamster.libraries.amplify.mclass.resources import MClassResource
from teamster.libraries.coupa.resources import CoupaResource
from teamster.libraries.email.resources import EmailResource
from teamster.libraries.google.directory.resources import GoogleDirectoryResource
from teamster.libraries.knowbe4.resources import KnowBe4Resource
from teamster.libraries.ldap.resources import LdapResource
from teamster.libraries.level_data.grow.resources import GrowResource
from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)
from teamster.libraries.smartrecruiters.resources import SmartRecruitersResource
from teamster.libraries.ssh.resources import SSHResource
from teamster.libraries.tableau.resources import TableauServerResource

ADP_WORKFORCE_NOW_RESOURCE = AdpWorkforceNowResource(
    client_id=EnvVar("ADP_WFN_CLIENT_ID"),
    client_secret=EnvVar("ADP_WFN_CLIENT_SECRET"),
    cert_filepath="/etc/secret-volume/adp_wfn_api.cer",
    key_filepath="/etc/secret-volume/adp_wfn_api.key",
    masked=False,
)

AIRBYTE_CLOUD_RESOURCE = AirbyteCloudWorkspace(
    workspace_id=EnvVar("AIRBYTE_WORKSPACE_ID"),
    client_id=EnvVar("AIRBYTE_CLIENT_ID"),
    client_secret=EnvVar("AIRBYTE_CLIENT_SECRET"),
)

COUPA_RESOURCE = CoupaResource(
    instance_url=EnvVar("COUPA_API_INSTANCE_URL"),
    client_id=EnvVar("COUPA_API_CLIENT_ID"),
    client_secret=EnvVar("COUPA_API_CLIENT_SECRET"),
    scope=["core.common.read", "core.user.read"],
)

OUTLOOK_RESOURCE = EmailResource(
    host=EnvVar("OUTLOOK_HOST"),
    port=int(check.not_none(value=EnvVar("OUTLOOK_PORT").get_value())),
    user=EnvVar("OUTLOOK_USER"),
    password=EnvVar("OUTLOOK_PASSWORD"),
    chunk_size=450,
)

GOOGLE_DIRECTORY_RESOURCE = GoogleDirectoryResource(
    customer_id=EnvVar("GOOGLE_WORKSPACE_CUSTOMER_ID"),
    delegated_account=EnvVar("GOOGLE_DIRECTORY_DELEGATED_ACCOUNT"),
)

KNOWBE4_RESOURCE = KnowBe4Resource(
    api_key=EnvVar("KNOWBE4_API_KEY"), server="us", page_size=500
)

LDAP_RESOURCE = LdapResource(
    host=EnvVar("LDAP_HOST_IP"),
    port=EnvVar("LDAP_PORT"),
    user=EnvVar("LDAP_USER"),
    password=EnvVar("LDAP_PASSWORD"),
)

MCLASS_RESOURCE = MClassResource(
    username=EnvVar("AMPLIFY_USERNAME"),
    password=EnvVar("AMPLIFY_PASSWORD"),
    request_timeout=(60 * 10),
)

POWERSCHOOL_ENROLLMENT_RESOURCE = PowerSchoolEnrollmentResource(
    api_key=EnvVar("PS_ENROLLMENT_API_KEY"), page_size=1000
)

GROW_RESOURCE = GrowResource(
    client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
    client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
    district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
    api_response_limit=3200,
)

SMARTRECRUITERS_RESOURCE = SmartRecruitersResource(
    smart_token=EnvVar("SMARTRECRUITERS_SMARTTOKEN")
)

TABLEAU_SERVER_RESOURCE = TableauServerResource(
    server_address=EnvVar("TABLEAU_SERVER_ADDRESS"),
    site_id=EnvVar("TABLEAU_SITE_ID"),
    token_name=EnvVar("TABLEAU_TOKEN_NAME"),
    personal_access_token=EnvVar("TABLEAU_PERSONAL_ACCESS_TOKEN"),
)

"""
SSH resources
"""

SSH_RESOURCE_ADP_WORKFORCE_NOW = SSHResource(
    remote_host=EnvVar("ADP_SFTP_HOST_IP"),
    remote_port=22,
    username=EnvVar("ADP_SFTP_USERNAME"),
    password=EnvVar("ADP_SFTP_PASSWORD"),
)

SSH_RESOURCE_CLEVER = SSHResource(
    remote_host=EnvVar("CLEVER_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("CLEVER_SFTP_USERNAME"),
    password=EnvVar("CLEVER_SFTP_PASSWORD"),
)

SSH_RESOURCE_COUPA = SSHResource(
    remote_host=EnvVar("COUPA_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("COUPA_SFTP_USERNAME"),
    password=EnvVar("COUPA_SFTP_PASSWORD"),
)

SSH_RESOURCE_DEANSLIST = SSHResource(
    remote_host=EnvVar("DEANSLIST_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("DEANSLIST_SFTP_USERNAME"),
    password=EnvVar("DEANSLIST_SFTP_PASSWORD"),
)

SSH_RESOURCE_EGENCIA = SSHResource(
    remote_host=EnvVar("EGENCIA_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("EGENCIA_SFTP_USERNAME"),
    key_file="/etc/secret-volume/id_rsa_egencia",
)

SSH_RESOURCE_ILLUMINATE = SSHResource(
    remote_host=EnvVar("ILLUMINATE_SFTP_HOST"),
    remote_port=22,
    username=EnvVar("ILLUMINATE_SFTP_USERNAME"),
    password=EnvVar("ILLUMINATE_SFTP_PASSWORD"),
)

SSH_RESOURCE_IDAUTO = SSHResource(
    remote_host=EnvVar("KTAF_SFTP_HOST_IP"),
    remote_port=22,
    username=EnvVar("KTAF_SFTP_USERNAME"),
    password=EnvVar("KTAF_SFTP_PASSWORD"),
)

SSH_RESOURCE_LITTLESIS = SSHResource(
    remote_host=EnvVar("LITTLESIS_SFTP_HOST"),
    remote_port=int(check.not_none(value=EnvVar("LITTLESIS_SFTP_PORT").get_value())),
    username=EnvVar("LITTLESIS_SFTP_USERNAME"),
    password=EnvVar("LITTLESIS_SFTP_PASSWORD"),
)
