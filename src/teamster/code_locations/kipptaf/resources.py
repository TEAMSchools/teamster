from dagster import EnvVar, _check
from dagster_airbyte import AirbyteCloudWorkspace
from dagster_dlt import DagsterDltResource
from dagster_fivetran import FivetranWorkspace

from teamster.libraries.adp.workforce_manager.resources import (
    AdpWorkforceManagerResource,
)
from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource
from teamster.libraries.amplify.dibels.resources import DibelsDataSystemResource
from teamster.libraries.amplify.mclass.resources import MClassResource
from teamster.libraries.coupa.resources import CoupaResource
from teamster.libraries.google.directory.resources import GoogleDirectoryResource
from teamster.libraries.google.drive.resources import GoogleDriveResource
from teamster.libraries.google.forms.resources import GoogleFormsResource
from teamster.libraries.google.sheets.resources import GoogleSheetsResource
from teamster.libraries.ldap.resources import LdapResource
from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)
from teamster.libraries.schoolmint.grow.resources import SchoolMintGrowResource
from teamster.libraries.smartrecruiters.resources import SmartRecruitersResource
from teamster.libraries.ssh.resources import SSHResource
from teamster.libraries.tableau.resources import TableauServerResource

"""
Dagster resources
"""

ADP_WORKFORCE_MANAGER_RESOURCE = AdpWorkforceManagerResource(
    subdomain=EnvVar("ADP_WFM_SUBDOMAIN"),
    app_key=EnvVar("ADP_WFM_APP_KEY"),
    client_id=EnvVar("ADP_WFM_CLIENT_ID"),
    client_secret=EnvVar("ADP_WFM_CLIENT_SECRET"),
    username=EnvVar("ADP_WFM_USERNAME"),
    password=EnvVar("ADP_WFM_PASSWORD"),
)

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

DIBELS_DATA_SYSTEM_RESOURCE = DibelsDataSystemResource(
    username=EnvVar("AMPLIFY_DDS_USERNAME"), password=EnvVar("AMPLIFY_DDS_PASSWORD")
)

DLT_RESOURCE = DagsterDltResource()

FIVETRAN_RESOURCE = FivetranWorkspace(
    account_id=EnvVar("FIVETRAN_ACCOUNT_ID"),
    api_key=EnvVar("FIVETRAN_API_KEY"),
    api_secret=EnvVar("FIVETRAN_API_SECRET"),
)

GOOGLE_DRIVE_RESOURCE = GoogleDriveResource(
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
)

GOOGLE_FORMS_RESOURCE = GoogleFormsResource(
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
)

GOOGLE_DIRECTORY_RESOURCE = GoogleDirectoryResource(
    customer_id=EnvVar("GOOGLE_WORKSPACE_CUSTOMER_ID"),
    delegated_account=EnvVar("GOOGLE_DIRECTORY_DELEGATED_ACCOUNT"),
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
)

GOOGLE_SHEETS_RESOURCE = GoogleSheetsResource(
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
)

LDAP_RESOURCE = LdapResource(
    host=EnvVar("LDAP_HOST_IP"),
    port=EnvVar("LDAP_PORT"),
    user=EnvVar("LDAP_USER"),
    password=EnvVar("LDAP_PASSWORD"),
)

MCLASS_RESOURCE = MClassResource(
    username=EnvVar("AMPLIFY_USERNAME"), password=EnvVar("AMPLIFY_PASSWORD")
)

POWERSCHOOL_ENROLLMENT_RESOURCE = PowerSchoolEnrollmentResource(
    api_key=EnvVar("PS_ENROLLMENT_API_KEY"), page_size=1000
)

SCHOOLMINT_GROW_RESOURCE = SchoolMintGrowResource(
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
    remote_port=int(_check.not_none(value=EnvVar("LITTLESIS_SFTP_PORT").get_value())),
    username=EnvVar("LITTLESIS_SFTP_USERNAME"),
    password=EnvVar("LITTLESIS_SFTP_PASSWORD"),
)
