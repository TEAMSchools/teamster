from dagster import Definitions, EnvVar, load_assets_from_modules
from dagster_airbyte import AirbyteCloudResource
from dagster_dbt import DbtCliResource
from dagster_fivetran import FivetranResource
from dagster_gcp import (
    BigQueryResource,
    ConfigurablePickledObjectGCSIOManager,
    GCSResource,
)
from dagster_k8s import k8s_job_executor

from teamster import GCS_PROJECT_NAME
from teamster.core.adp.resources import (
    AdpWorkforceManagerResource,
    AdpWorkforceNowResource,
)
from teamster.core.alchemer.resources import AlchemerResource
from teamster.core.amplify.resources import MClassResource
from teamster.core.google.directory.resources import GoogleDirectoryResource
from teamster.core.google.forms.resources import GoogleFormsResource
from teamster.core.google.io.resources import gcs_io_manager
from teamster.core.google.sheets.resources import GoogleSheetsResource
from teamster.core.ldap.resources import LdapResource
from teamster.core.schoolmint.grow.resources import SchoolMintGrowResource
from teamster.core.smartrecruiters.resources import SmartRecruitersResource
from teamster.core.ssh.resources import SSHResource
from teamster.core.utils.jobs import asset_observation_job
from teamster.kipptaf import (
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

resource_config_dir = f"src/teamster/{CODE_LOCATION}/config/resources"

defs = Definitions(
    executor=k8s_job_executor,
    assets=[
        *load_assets_from_modules(modules=[achieve3k], group_name="achieve3k"),
        *load_assets_from_modules(modules=[adp], group_name="adp"),
        *load_assets_from_modules(modules=[alchemer], group_name="alchemer"),
        *load_assets_from_modules(modules=[amplify], group_name="amplify"),
        *load_assets_from_modules(modules=[clever], group_name="clever"),
        *load_assets_from_modules(modules=[datagun], group_name="datagun"),
        *load_assets_from_modules(modules=[dayforce], group_name="dayforce"),
        *load_assets_from_modules(modules=[dbt]),
        *load_assets_from_modules(modules=[google], group_name="google"),
        *load_assets_from_modules(modules=[ldap], group_name="ldap"),
        *load_assets_from_modules(modules=[schoolmint], group_name="schoolmint_grow"),
        *load_assets_from_modules(
            modules=[smartrecruiters], group_name="smartrecruiters"
        ),
        *load_assets_from_modules(modules=[airbyte]),
        *load_assets_from_modules(modules=[fivetran]),
    ],
    jobs=[
        *adp.jobs,
        *airbyte.jobs,
        *amplify.jobs,
        *datagun.jobs,
        *fivetran.jobs,
        *google.jobs,
        *schoolmint.jobs,
        *smartrecruiters.jobs,
        asset_observation_job,
    ],
    schedules=[
        *adp.schedules,
        *airbyte.schedules,
        *amplify.schedules,
        *datagun.schedules,
        *dbt.schedules,
        *fivetran.schedules,
        *google.schedules,
        *ldap.schedules,
        *schoolmint.schedules,
        *smartrecruiters.schedules,
    ],
    sensors=[
        *achieve3k.sensors,
        *adp.sensors,
        *airbyte.sensors,
        *alchemer.sensors,
        *clever.sensors,
        *fivetran.sensors,
        *google.sensors,
    ],
    resources={
        "io_manager": ConfigurablePickledObjectGCSIOManager(
            gcs=GCSResource(project=GCS_PROJECT_NAME), gcs_bucket="teamster-kipptaf"
        ),
        "io_manager_gcs_avro": gcs_io_manager.configured(
            config_or_config_fn={
                "gcs_bucket": f"teamster-{CODE_LOCATION}",
                "io_format": "avro",
            }
        ),
        "gcs": GCSResource(project=GCS_PROJECT_NAME),
        "dbt_cli": DbtCliResource(project_dir=f"src/dbt/{CODE_LOCATION}"),
        "db_bigquery": BigQueryResource(project=GCS_PROJECT_NAME),
        "adp_wfm": AdpWorkforceManagerResource(
            subdomain=EnvVar("ADP_WFM_SUBDOMAIN"),
            app_key=EnvVar("ADP_WFM_APP_KEY"),
            client_id=EnvVar("ADP_WFM_CLIENT_ID"),
            client_secret=EnvVar("ADP_WFM_CLIENT_SECRET"),
            username=EnvVar("ADP_WFM_USERNAME"),
            password=EnvVar("ADP_WFM_PASSWORD"),
        ),
        "adp_wfn": AdpWorkforceNowResource(
            client_id=EnvVar("ADP_WFN_CLIENT_ID"),
            client_secret=EnvVar("ADP_WFN_CLIENT_SECRET"),
            cert_filepath="/etc/secret-volume/adp_wfn_cert",
            key_filepath="/etc/secret-volume/adp_wfn_key",
        ),
        "airbyte": AirbyteCloudResource(api_key=EnvVar("AIRBYTE_API_KEY")),
        "alchemer": AlchemerResource(
            api_token=EnvVar("ALCHEMER_API_TOKEN"),
            api_token_secret=EnvVar("ALCHEMER_API_TOKEN_SECRET"),
            api_version="v5",
        ),
        "fivetran": FivetranResource(
            api_key=EnvVar("FIVETRAN_API_KEY"), api_secret=EnvVar("FIVETRAN_API_SECRET")
        ),
        "google_forms": GoogleFormsResource(
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
        ),
        "google_directory": GoogleDirectoryResource(
            customer_id="C029u7m0n",
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json",
            delegated_account="dagster@apps.teamschools.org",
        ),
        "gsheets": GoogleSheetsResource(
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
        ),
        "ldap": LdapResource(
            host="ldap1.kippnj.org",
            port=636,
            user=EnvVar("LDAP_USER"),
            password=EnvVar("LDAP_PASSWORD"),
        ),
        "mclass": MClassResource(
            username=EnvVar("AMPLIFY_USERNAME"), password=EnvVar("AMPLIFY_PASSWORD")
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
        "ssh_achieve3k": SSHResource(
            remote_host="xfer.achieve3000.com",
            username=EnvVar("ACHIEVE3K_SFTP_USERNAME"),
            password=EnvVar("ACHIEVE3K_SFTP_PASSWORD"),
        ),
        "ssh_adp_workforce_now": SSHResource(
            remote_host="sftp.kippnj.org",
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
            remote_host="sftp.kippnj.org",
            username=EnvVar("KTAF_SFTP_USERNAME"),
            password=EnvVar("KTAF_SFTP_PASSWORD"),
        ),
        "ssh_idauto": SSHResource(
            remote_host="sftp.kippnj.org",
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
