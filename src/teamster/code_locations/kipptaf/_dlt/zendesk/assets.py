from dagster import EnvVar, _check

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.dlt.zendesk.assets import build_zendesk_support_dlt_assets
from teamster.libraries.dlt.zendesk.pipeline.helpers.credentials import (
    ZendeskCredentialsToken,
)

zendesk_credentials = ZendeskCredentialsToken(
    subdomain=_check.not_none(value=EnvVar("ZENDESK_SUBDOMAIN").get_value()),
    email=_check.not_none(value=EnvVar("ZENDESK_EMAIL").get_value()),
    token=EnvVar("ZENDESK_TOKEN").get_value(),
)

assets = [
    build_zendesk_support_dlt_assets(
        zendesk_credentials=zendesk_credentials, code_location=CODE_LOCATION
    ),
]
