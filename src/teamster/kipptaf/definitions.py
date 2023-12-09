from dagster import Definitions, EnvVar, load_assets_from_modules
from dagster_airbyte import AirbyteCloudResource
from dagster_dbt import DbtCliResource
from dagster_fivetran import FivetranResource
from dagster_gcp import BigQueryResource, GCSResource
from dagster_k8s import k8s_job_executor

from teamster import GCS_PROJECT_NAME
from teamster.core.google.storage.io_manager import GCSIOManager
from teamster.core.ssh.resources import SSHResource

from . import (
    CODE_LOCATION,
    achieve3k,
    adp,
    airbyte,
    alchemer,
    amplify,
    clever,
    datagun,
    dayforce,
    dbt,
    fivetran,
    google,
    ldap,
    schoolmint,
    smartrecruiters,
)

GCS_RESOURCE = GCSResource(project=GCS_PROJECT_NAME)

defs = Definitions(
    executor=k8s_job_executor,
    assets=load_assets_from_modules(
        modules=[
            achieve3k,
            adp.workforce_manager,
            adp.workforce_now,
            airbyte,
            alchemer,
            amplify,
            clever,
            datagun,
            dayforce,
            dbt,
            fivetran,
            google.directory,
            google.forms,
            google.sheets,
            ldap,
            schoolmint,
            smartrecruiters,
        ]
    ),
    schedules=[
        *adp.workforce_manager.schedules,
        *adp.workforce_now.schedules,
        *airbyte.schedules,
        *amplify.schedules,
        *datagun.schedules,
        *dbt.schedules,
        *fivetran.schedules,
        *google.forms.schedules,
        *google.directory.schedules,
        *ldap.schedules,
        *schoolmint.schedules,
        *smartrecruiters.schedules,
    ],
    sensors=[
        *achieve3k.sensors,
        *adp.workforce_now.sensors,
        *airbyte.sensors,
        *alchemer.sensors,
        *clever.sensors,
        *fivetran.sensors,
        *google.sheets.sensors,
    ],
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
        "dbt_cli": DbtCliResource(project_dir=f"src/dbt/{CODE_LOCATION}"),
        "db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME),
        "adp_wfm": adp.workforce_manager.resources.AdpWorkforceManagerResource(
            subdomain=EnvVar("ADP_WFM_SUBDOMAIN"),
            app_key=EnvVar("ADP_WFM_APP_KEY"),
            client_id=EnvVar("ADP_WFM_CLIENT_ID"),
            client_secret=EnvVar("ADP_WFM_CLIENT_SECRET"),
            username=EnvVar("ADP_WFM_USERNAME"),
            password=EnvVar("ADP_WFM_PASSWORD"),
        ),
        "adp_wfn": adp.workforce_now.resources.AdpWorkforceNowResource(
            client_id=EnvVar("ADP_WFN_CLIENT_ID"),
            client_secret=EnvVar("ADP_WFN_CLIENT_SECRET"),
            cert_filepath="/etc/secret-volume/adp_wfn_cert",
            key_filepath="/etc/secret-volume/adp_wfn_key",
        ),
        "airbyte": AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY")),
        "alchemer": alchemer.resources.AlchemerResource(
            api_token=EnvVar("ALCHEMER_API_TOKEN"),
            api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
            api_version="v5",
        ),
        "fivetran": FivetranResource(
            api_key=EnvVar("FIVETRAN_API_KEY"), api_secret=EnvVar("FIVETRAN_API_SECRET")
        ),
        "google_forms": google.forms.resources.GoogleFormsResource(
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
        ),
        "google_directory": google.directory.resources.GoogleDirectoryResource(
            customer_id="C029u7m0n",
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
            delegated_account="dagster@apps.teamschools.org",
        ),
        "gsheets": google.sheets.resources.GoogleSheetsResource(
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
        ),
        "ldap": ldap.resources.LdapResource(
            # host="ldap1.kippnj.org",
            host="204.8.89.213",
            port=636,
            user=EnvVar("LDAP_USER"),
            password=EnvVar("LDAP_PASSWORD"),
        ),
        "mclass": amplify.resources.MClassResource(
            username=EnvVar("AMPLIFY_USERNAME"), password=EnvVar("AMPLIFY_PASSWORD")
        ),
        "schoolmint_grow": schoolmint.grow.resources.SchoolMintGrowResource(
            client_id=EnvVar("SCHOOLMINT_GROW_CLIENT_ID"),
            client_secret=EnvVar("SCHOOLMINT_GROW_CLIENT_SECRET"),
            district_id=EnvVar("SCHOOLMINT_GROW_DISTRICT_ID"),
            api_response_limit=3200,
        ),
        "smartrecruiters": smartrecruiters.resources.SmartRecruitersResource(
            smart_token=EnvVar("SMARTRECRUITERS_SMARTTOKEN")
        ),
        "ssh_achieve3k": SSHResource(
            remote_host="xfer.achieve3000.com",
            username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
            password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
        ),
        "ssh_adp_workforce_now": SSHResource(
            # remote_host="sftp.kippnj.org",
            remote_host="204.8.89.221",
            username=EnvVar("ADP_SFTP_USERNAME"),
            password=EnvVar("ADP_SFTP_PASSWORD"),
        ),
        "ssh_blissbook": SSHResource(
            remote_host="sftp.blissbook.com",
            remote_port=3022,
            username=EnvVar("BLISSBOOK_SFTP_USERNAME"),
            password=EnvVar("BLISSBOOK_SFTP_PASSWORD"),
        ),
        "ssh_clever": SSHResource(
            remote_host="sftp.clever.com",
            username=EnvVar("CLEVER_SFTP_USERNAME"),
            password=EnvVar("CLEVER_SFTP_PASSWORD"),
        ),
        "ssh_clever_reports": SSHResource(
            remote_host="reports-sftp.clever.com",
            username=EnvVar("CLEVER_REPORTS_SFTP_USERNAME"),
            password=EnvVar("CLEVER_REPORTS_SFTP_PASSWORD"),
        ),
        "ssh_couchdrop": SSHResource(
            remote_host="kipptaf.couchdrop.io",
            username=EnvVar("COUCHDROP_SFTP_USERNAME"),
            password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
        ),
        "ssh_coupa": SSHResource(
            remote_host="fileshare.coupahost.com",
            username=EnvVar("COUPA_SFTP_USERNAME"),
            password=EnvVar("COUPA_SFTP_PASSWORD"),
        ),
        "ssh_deanslist": SSHResource(
            remote_host="sftp.deanslistsoftware.com",
            username=EnvVar("DEANSLIST_SFTP_USERNAME"),
            password=EnvVar("DEANSLIST_SFTP_PASSWORD"),
        ),
        "ssh_egencia": SSHResource(
            remote_host="eusftp.egencia.com",
            username=EnvVar("EGENCIA_SFTP_USERNAME"),
            key_file="/etc/secret-volume/id_rsa_egencia",
        ),
        "ssh_illuminate": SSHResource(
            remote_host="sftp.illuminateed.com",
            username=EnvVar("ILLUMINATE_SFTP_USERNAME"),
            password=EnvVar("ILLUMINATE_SFTP_PASSWORD"),
        ),
        "ssh_kipptaf": SSHResource(
            # remote_host="sftp.kippnj.org",
            remote_host="204.8.89.221",
            username=EnvVar("KTAF_SFTP_USERNAME"),
            password=EnvVar("KTAF_SFTP_PASSWORD"),
        ),
        "ssh_idauto": SSHResource(
            # remote_host="sftp.kippnj.org",
            remote_host="204.8.89.221",
            username=EnvVar("KTAF_SFTP_USERNAME"),
            password=EnvVar("KTAF_SFTP_PASSWORD"),
        ),
        "ssh_littlesis": SSHResource(
            remote_host="upload.littlesis.app",
            username=EnvVar("LITTLESIS_SFTP_USERNAME"),
            password=EnvVar("LITTLESIS_SFTP_PASSWORD"),
        ),
        "ssh_pythonanywhere": SSHResource(
            remote_host="ssh.pythonanywhere.com",
            username=EnvVar("PYTHONANYWHERE_SFTP_USERNAME"),
            password=EnvVar("PYTHONANYWHERE_SFTP_PASSWORD"),
        ),
        "ssh_razkids": SSHResource(
            remote_host="sftp.learninga-z.com",
            remote_port=22224,
            username=EnvVar("RAZKIDS_SFTP_USERNAME"),
            password=EnvVar("RAZKIDS_SFTP_PASSWORD"),
        ),
        "ssh_read180": SSHResource(
            remote_host="imports.education.scholastic.com",
            username=EnvVar("READ180_SFTP_USERNAME"),
            password=EnvVar("READ180_SFTP_PASSWORD"),
        ),
    },
)
