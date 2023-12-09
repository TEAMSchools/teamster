from dagster import EnvVar
from dagster_airbyte import AirbyteCloudResource
from dagster_fivetran import FivetranResource

from teamster.core.ssh.resources import SSHResource

from . import adp, alchemer, amplify, google, ldap, schoolmint, smartrecruiters

ADP_WORKFORCE_MANAGER_RESOURCE = (
    adp.workforce_manager.resources.AdpWorkforceManagerResource(
        subdomain=EnvVar("ADP_WFM_SUBDOMAIN"),
        app_key=EnvVar("ADP_WFM_APP_KEY"),
        client_id=EnvVar("ADP_WFM_CLIENT_ID"),
        client_secret=EnvVar("ADP_WFM_CLIENT_SECRET"),
        username=EnvVar("ADP_WFM_USERNAME"),
        password=EnvVar("ADP_WFM_PASSWORD"),
    )
)

ADP_WORKFORCE_NOW_RESOURCE = adp.workforce_now.resources.AdpWorkforceNowResource(
    client_id=EnvVar("ADP_WFN_CLIENT_ID"),
    client_secret=EnvVar("ADP_WFN_CLIENT_SECRET"),
    cert_filepath="/etc/secret-volume/adp_wfn_cert",
    key_filepath="/etc/secret-volume/adp_wfn_key",
)

AIRBYTE_CLOUD_RESOURCE = AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY"))

ALCHEMER_RESOURCE = alchemer.resources.AlchemerResource(
    api_token=EnvVar("ALCHEMER_API_TOKEN"),
    api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
    api_version="v5",
)

FIVETRAN_RESOURCE = FivetranResource(
    api_key=EnvVar("FIVETRAN_API_KEY"), api_secret=EnvVar("FIVETRAN_API_SECRET")
)

GOOGLE_FORMS_RESOURCE = google.forms.resources.GoogleFormsResource(
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
)

GOOGLE_DIRECTORY_RESOURCE = google.directory.resources.GoogleDirectoryResource(
    customer_id="C029u7m0n",
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
    delegated_account="dagster@apps.teamschools.org",
)

GOOGLE_SHEETS_RESOURCE = google.sheets.resources.GoogleSheetsResource(
    service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
)

LDAP_RESOURCE = ldap.resources.LdapResource(
    # host="ldap1.kippnj.org",
    host="204.8.89.213",
    port=636,
    user=EnvVar("LDAP_USER"),
    password=EnvVar("LDAP_PASSWORD"),
)

MCLASS_RESOURCE = amplify.resources.MClassResource(
    username=EnvVar("AMPLIFY_USERNAME"), password=EnvVar("AMPLIFY_PASSWORD")
)

SCHOOLMINT_GROW_RESOURCE = schoolmint.grow.resources.SchoolMintGrowResource(
    client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
    client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
    district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
    api_response_limit=3200,
)

SMARTRECRUITERS_RESOURCE = smartrecruiters.resources.SmartRecruitersResource(
    smart_token=EnvVar("SMARTRECRUITERS_SMARTTOKEN")
)

SSH_RESOURCE_ACHIEVE3K = SSHResource(
    remote_host="xfer.achieve3000.com",
    username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
    password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
)

SSH_RESOURCE_ADP_WORKFORCE_NOW = SSHResource(
    # remote_host="sftp.kippnj.org",
    remote_host="204.8.89.221",
    username=EnvVar("ADP_SFTP_USERNAME"),
    password=EnvVar("ADP_SFTP_PASSWORD"),
)

SSH_RESOURCE_BLISSBOOK = SSHResource(
    remote_host="sftp.blissbook.com",
    remote_port=3022,
    username=EnvVar("BLISSBOOK_SFTP_USERNAME"),
    password=EnvVar("BLISSBOOK_SFTP_PASSWORD"),
)

SSH_RESOURCE_CLEVER = SSHResource(
    remote_host="sftp.clever.com",
    username=EnvVar("CLEVER_SFTP_USERNAME"),
    password=EnvVar("CLEVER_SFTP_PASSWORD"),
)

SSH_RESOURCE_CLEVER_REPORTS = SSHResource(
    remote_host="reports-sftp.clever.com",
    username=EnvVar("CLEVER_REPORTS_SFTP_USERNAME"),
    password=EnvVar("CLEVER_REPORTS_SFTP_PASSWORD"),
)

SSH_RESOURCE_COUPA = SSHResource(
    remote_host="fileshare.coupahost.com",
    username=EnvVar("COUPA_SFTP_USERNAME"),
    password=EnvVar("COUPA_SFTP_PASSWORD"),
)

SSH_RESOURCE_DEANSLIST = SSHResource(
    remote_host="sftp.deanslistsoftware.com",
    username=EnvVar("DEANSLIST_SFTP_USERNAME"),
    password=EnvVar("DEANSLIST_SFTP_PASSWORD"),
)

SSH_RESOURCE_EGENCIA = SSHResource(
    remote_host="eusftp.egencia.com",
    username=EnvVar("EGENCIA_SFTP_USERNAME"),
    key_file="/etc/secret-volume/id_rsa_egencia",
)

SSH_RESOURCE_ILLUMINATE = SSHResource(
    remote_host="sftp.illuminateed.com",
    username=EnvVar("ILLUMINATE_SFTP_USERNAME"),
    password=EnvVar("ILLUMINATE_SFTP_PASSWORD"),
)

SSH_RESOURCE_IDAUTO = SSHResource(
    # remote_host="sftp.kippnj.org",
    remote_host="204.8.89.221",
    username=EnvVar("KTAF_SFTP_USERNAME"),
    password=EnvVar("KTAF_SFTP_PASSWORD"),
)

SSH_RESOURCE_LITTLESIS = SSHResource(
    remote_host="upload.littlesis.app",
    username=EnvVar("LITTLESIS_SFTP_USERNAME"),
    password=EnvVar("LITTLESIS_SFTP_PASSWORD"),
)
