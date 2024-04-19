import os
import pathlib

from dagster import AssetExecutionContext, asset

ENVS = [
    "ADP_SFTP_PASSWORD",
    "ADP_SFTP_USERNAME",
    "ADP_WFM_APP_KEY",
    "ADP_WFM_CLIENT_ID",
    "ADP_WFM_CLIENT_SECRET",
    "ADP_WFM_PASSWORD",
    "ADP_WFM_SUBDOMAIN",
    "ADP_WFM_USERNAME",
    "ADP_WFN_CLIENT_ID",
    "ADP_WFN_CLIENT_SECRET",
    "AIRBYTE_API_KEY",
    "ALCHEMER_API_TOKEN_SECRET",
    "ALCHEMER_API_TOKEN",
    "AMPLIFY_PASSWORD",
    "AMPLIFY_USERNAME",
    "BLISSBOOK_SFTP_PASSWORD",
    "BLISSBOOK_SFTP_USERNAME",
    "CLEVER_SFTP_PASSWORD",
    "CLEVER_SFTP_USERNAME",
    "COUCHDROP_SFTP_PASSWORD",
    "COUCHDROP_SFTP_USERNAME",
    "COUPA_SFTP_PASSWORD",
    "COUPA_SFTP_USERNAME",
    "DEANSLIST_SFTP_PASSWORD",
    "DEANSLIST_SFTP_USERNAME",
    "EDPLAN_SFTP_PASSWORD",
    "EDPLAN_SFTP_USERNAME",
    "EGENCIA_SFTP_USERNAME",
    "FIVETRAN_API_KEY",
    "FIVETRAN_API_SECRET",
    "ILLUMINATE_SFTP_PASSWORD",
    "ILLUMINATE_SFTP_USERNAME",
    "IREADY_SFTP_PASSWORD",
    "IREADY_SFTP_USERNAME",
    "KTAF_SFTP_PASSWORD",
    "KTAF_SFTP_USERNAME",
    "LDAP_PASSWORD",
    "LDAP_USER",
    "LITTLESIS_SFTP_PASSWORD",
    "LITTLESIS_SFTP_USERNAME",
    "PS_DB_PASSWORD",
    "PS_SSH_PASSWORD",
    "PS_SSH_PORT",
    "PS_SSH_REMOTE_BIND_HOST",
    "PS_SSH_USERNAME",
    "RENLEARN_SFTP_PASSWORD",
    "RENLEARN_SFTP_USERNAME",
    "SCHOOLMINT_GROW_CLIENT_ID",
    "SCHOOLMINT_GROW_CLIENT_SECRET",
    "SCHOOLMINT_GROW_DISTRICT_ID",
    "SMARTRECRUITERS_SMARTTOKEN",
    "TITAN_SFTP_PASSWORD",
    "TITAN_SFTP_USERNAME",
    "ZENDESK_EMAIL",
    "ZENDESK_TOKEN",
]

FILES = [
    "/etc/secret-volume/id_rsa_egencia",
    "/etc/secret-volume/gcloud_service_account_json",
    "/etc/secret-volume/adp_wfn_key",
    "/etc/secret-volume/adp_wfn_cert",
    "/etc/secret-volume/deanslist_api_key_map_yaml",
    "/etc/secret-volume/dbt_user_creds_json",
]


@asset
def onepassword_secret_test(context: AssetExecutionContext):
    for key in ENVS:
        value = os.getenv(key)

        if value is None:
            context.log.error(msg=key)
        else:
            context.log.info(msg=value)

    for file in FILES:
        path = pathlib.Path(file)

        text = path.read_text()

        if text is None:
            context.log.error(msg=path)
        else:
            context.log.info(msg=text)
