from dagster import EnvVar
from dagster_shared import check
from simple_salesforce.api import Salesforce
from simple_salesforce.login import SalesforceLogin


def test_foo():
    session_id, instance = SalesforceLogin(
        username=check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_USER_NAME").get_value()
        ),
        password=check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_PASSWORD").get_value()
        ),
        security_token=check.not_none(
            value=EnvVar("SALESFORCE_KIPPADB_SECURITY_TOKEN").get_value()
        ),
    )

    client = Salesforce(session_id=session_id, instance=instance)

    client.describe()
