import json

from dagster import EnvVar, _check

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.dlt.salesforce.assets import build_salesforce_kippadb_dlt_assets

dlt_credentials = json.load(
    fp=open(file="/etc/secret-volume/gcloud_teamster_dlt_keyfile.json")
)

assets = [
    build_salesforce_kippadb_dlt_assets(
        salesforce_user_name=_check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_USER_NAME").get_value()
        ),
        salesforce_password=_check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_PASSWORD").get_value()
        ),
        salesforce_security_token=_check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_SECURITY_TOKEN").get_value()
        ),
        dlt_credentials=dlt_credentials,
        code_location=CODE_LOCATION,
    ),
]
