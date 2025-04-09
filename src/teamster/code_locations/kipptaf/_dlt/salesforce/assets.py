from dagster import EnvVar
from dagster_shared import check

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.libraries.dlt.salesforce.assets import build_salesforce_kippadb_dlt_assets

assets = [
    build_salesforce_kippadb_dlt_assets(
        salesforce_user_name=check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_USER_NAME").get_value()
        ),
        salesforce_password=check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_PASSWORD").get_value()
        ),
        salesforce_security_token=check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_SECURITY_TOKEN").get_value()
        ),
        code_location=CODE_LOCATION,
    ),
]
