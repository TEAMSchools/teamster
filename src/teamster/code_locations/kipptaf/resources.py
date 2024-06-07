from dagster import EnvVar
from dagster_airbyte import AirbyteCloudResource
from dagster_fivetran import FivetranResource

from teamster.libraries.adp.workforce_manager.resources import (
    AdpWorkforceManagerResource,
)
from teamster.libraries.adp.workforce_now.api.resources import AdpWorkforceNowResource
from teamster.libraries.alchemer.resources import AlchemerResource
from teamster.libraries.amplify.dibels.resources import DibelsDataSystemResource
from teamster.libraries.amplify.mclass.resources import MClassResource
from teamster.libraries.google.directory.resources import GoogleDirectoryResource
from teamster.libraries.google.drive.resources import GoogleDriveResource
from teamster.libraries.google.forms.resources import GoogleFormsResource
from teamster.libraries.google.sheets.resources import GoogleSheetsResource
from teamster.libraries.ldap.resources import LdapResource
from teamster.libraries.overgrad.resources import OvergradResource
from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)
from teamster.libraries.schoolmint.grow.resources import SchoolMintGrowResource
from teamster.libraries.smartrecruiters.resources import SmartRecruitersResource
from teamster.libraries.ssh.resources import SSHResource
from teamster.libraries.tableau.resources import TableauServerResource
from teamster.libraries.zendesk.resources import ZendeskResource

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
    cert_filepath="/etc/secret-volume/adp_wfn_cert",
    key_filepath="/etc/secret-volume/adp_wfn_key",
)

AIRBYTE_CLOUD_RESOURCE = AirbyteCloudResource(
    api_key=EnvVar("AIRBYTE_API_KEY"), request_max_retries=2, request_timeout=6
)

ALCHEMER_RESOURCE = AlchemerResource(
    api_token=EnvVar("ALCHEMER_API_TOKEN"),
    api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
    api_version="v5",
    timeout=15,
)

DIBELS_DATA_SYSTEM_RESOURCE = DibelsDataSystemResource(
    username=EnvVar("AMPLIFY_DDS_USERNAME"), password=EnvVar("AMPLIFY_DDS_PASSWORD")
)

FIVETRAN_RESOURCE = FivetranResource(
    api_key=EnvVar("FIVETRAN_API_KEY"), api_secret=EnvVar("FIVETRAN_API_SECRET")
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

OVERGRAD_RESOURCE = OvergradResource(api_key=EnvVar("OVERGRAD_API_KEY"), page_limit=100)

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

ZENDESK_RESOURCE = ZendeskResource(
    subdomain=EnvVar("ZENDESK_SUBDOMAIN"),
    email=EnvVar("ZENDESK_EMAIL"),
    token=EnvVar("ZENDESK_TOKEN"),
)

"""
SSH resources
"""

SSH_RESOURCE_ADP_WORKFORCE_NOW = SSHResource(
    remote_host=EnvVar("ADP_SFTP_HOST_IP"),
    username=EnvVar("ADP_SFTP_USERNAME"),
    password=EnvVar("ADP_SFTP_PASSWORD"),
)

SSH_RESOURCE_CLEVER = SSHResource(
    remote_host=EnvVar("CLEVER_SFTP_HOST"),
    username=EnvVar("CLEVER_SFTP_USERNAME"),
    password=EnvVar("CLEVER_SFTP_PASSWORD"),
)

SSH_RESOURCE_COUPA = SSHResource(
    remote_host=EnvVar("COUPA_SFTP_HOST"),
    username=EnvVar("COUPA_SFTP_USERNAME"),
    password=EnvVar("COUPA_SFTP_PASSWORD"),
)

SSH_RESOURCE_DEANSLIST = SSHResource(
    remote_host=EnvVar("DEANSLIST_SFTP_HOST"),
    username=EnvVar("DEANSLIST_SFTP_USERNAME"),
    password=EnvVar("DEANSLIST_SFTP_PASSWORD"),
)

SSH_RESOURCE_EGENCIA = SSHResource(
    remote_host=EnvVar("EGENCIA_SFTP_HOST"),
    username=EnvVar("EGENCIA_SFTP_USERNAME"),
    key_file="/etc/secret-volume/id_rsa_egencia",
)

SSH_RESOURCE_ILLUMINATE = SSHResource(
    remote_host=EnvVar("ILLUMINATE_SFTP_HOST"),
    username=EnvVar("ILLUMINATE_SFTP_USERNAME"),
    password=EnvVar("ILLUMINATE_SFTP_PASSWORD"),
)

SSH_RESOURCE_IDAUTO = SSHResource(
    remote_host=EnvVar("KTAF_SFTP_HOST_IP"),
    username=EnvVar("KTAF_SFTP_USERNAME"),
    password=EnvVar("KTAF_SFTP_PASSWORD"),
)

SSH_RESOURCE_BLISSBOOK = SSHResource(
    remote_host=EnvVar("BLISSBOOK_SFTP_HOST"),
    remote_port=EnvVar("BLISSBOOK_SFTP_PORT"),
    username=EnvVar("BLISSBOOK_SFTP_USERNAME"),
    password=EnvVar("BLISSBOOK_SFTP_PASSWORD"),
)

SSH_RESOURCE_LITTLESIS = SSHResource(
    remote_host=EnvVar("LITTLESIS_SFTP_HOST"),
    remote_port=EnvVar("LITTLESIS_SFTP_PORT"),
    username=EnvVar("LITTLESIS_SFTP_USERNAME"),
    password=EnvVar("LITTLESIS_SFTP_PASSWORD"),
)
