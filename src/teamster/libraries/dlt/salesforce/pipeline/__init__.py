"""Source for Salesforce depending on the simple_salesforce python package.

Imported resources are: account, campaign, contact, lead, opportunity, pricebook_2,
pricebook_entry, product_2, user and user_role

Salesforce api docs: https://developer.salesforce.com/docs/apis

To get the security token: https://onlinehelp.coveo.com/en/ces/7.0/administrator/getting_the_security_token_for_your_salesforce_account.htm
"""

from typing import Iterable

import dlt
from dlt.common.typing import TDataItem
from dlt.sources import DltResource, incremental
from simple_salesforce.api import Salesforce

from teamster.libraries.dlt.salesforce.pipeline.helpers import get_records


@dlt.source(name="salesforce")
def salesforce_source(
    user_name: str = dlt.secrets.value,
    password: str = dlt.secrets.value,
    security_token: str = dlt.secrets.value,
) -> Iterable[DltResource]:
    """
    Retrieves data from Salesforce using the Salesforce API.

    Args:
        user_name (str): The username for authentication.
            Defaults to the value in the `dlt.secrets` object.
        password (str): The password for authentication.
            Defaults to the value in the `dlt.secrets` object.
        security_token (str): The security token for authentication.
            Defaults to the value in the `dlt.secrets` object.

    Yields:
        DltResource: Data resources from Salesforce.
    """

    client = Salesforce(
        username=user_name, password=password, security_token=security_token
    )

    opportunity_last_timestamp = dlt.sources.incremental(
        cursor_path="SystemModstamp", initial_value=None
    )
    opportunity_line_item_last_timestamp = dlt.sources.incremental(
        cursor_path="SystemModstamp", initial_value=None
    )
    opportunity_contact_role_last_timestamp = dlt.sources.incremental(
        cursor_path="SystemModstamp", initial_value=None
    )
    account_last_timestamp = dlt.sources.incremental(
        cursor_path="LastModifiedDate", initial_value=None
    )
    campaign_member_last_timestamp = dlt.sources.incremental(
        cursor_path="SystemModstamp", initial_value=None
    )
    task_last_timestamp = dlt.sources.incremental(
        cursor_path="SystemModstamp", initial_value=None
    )
    event_last_timestamp = dlt.sources.incremental(
        cursor_path="SystemModstamp", initial_value=None
    )

    # define resources
    @dlt.resource(write_disposition="replace")
    def sf_user() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="User")

    @dlt.resource(write_disposition="replace")
    def user_role() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="UserRole")

    @dlt.resource(write_disposition="merge")
    def opportunity(
        last_timestamp: incremental = opportunity_last_timestamp,
    ) -> Iterable[TDataItem]:
        yield get_records(
            sf=client,
            sobject="Opportunity",
            last_state=last_timestamp.last_value,
            replication_key="SystemModstamp",
        )

    @dlt.resource(write_disposition="merge")
    def opportunity_line_item(
        last_timestamp: incremental = opportunity_line_item_last_timestamp,
    ) -> Iterable[TDataItem]:
        yield get_records(
            sf=client,
            sobject="OpportunityLineItem",
            last_state=last_timestamp.last_value,
            replication_key="SystemModstamp",
        )

    @dlt.resource(write_disposition="merge")
    def opportunity_contact_role(
        last_timestamp: incremental = opportunity_contact_role_last_timestamp,
    ) -> Iterable[TDataItem]:
        yield get_records(
            sf=client,
            sobject="OpportunityContactRole",
            last_state=last_timestamp.last_value,
            replication_key="SystemModstamp",
        )

    @dlt.resource(write_disposition="merge")
    def account(
        last_timestamp: incremental = account_last_timestamp,
    ) -> Iterable[TDataItem]:
        yield get_records(
            sf=client,
            sobject="Account",
            last_state=last_timestamp.last_value,
            replication_key="LastModifiedDate",
        )

    @dlt.resource(write_disposition="replace")
    def contact() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="Contact")

    @dlt.resource(write_disposition="replace")
    def lead() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="Lead")

    @dlt.resource(write_disposition="replace")
    def campaign() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="Campaign")

    @dlt.resource(write_disposition="merge")
    def campaign_member(
        last_timestamp: incremental = campaign_member_last_timestamp,
    ) -> Iterable[TDataItem]:
        yield get_records(
            sf=client,
            sobject="CampaignMember",
            last_state=last_timestamp.last_value,
            replication_key="SystemModstamp",
        )

    @dlt.resource(write_disposition="replace")
    def product_2() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="Product2")

    @dlt.resource(write_disposition="replace")
    def pricebook_2() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="Pricebook2")

    @dlt.resource(write_disposition="replace")
    def pricebook_entry() -> Iterable[TDataItem]:
        yield get_records(sf=client, sobject="PricebookEntry")

    @dlt.resource(write_disposition="merge")
    def task(last_timestamp: incremental = task_last_timestamp) -> Iterable[TDataItem]:
        yield get_records(
            sf=client,
            sobject="Task",
            last_state=last_timestamp.last_value,
            replication_key="SystemModstamp",
        )

    @dlt.resource(write_disposition="merge")
    def event(
        last_timestamp: incremental = event_last_timestamp,
    ) -> Iterable[TDataItem]:
        yield get_records(
            sf=client,
            sobject="Event",
            last_state=last_timestamp.last_value,
            replication_key="SystemModstamp",
        )

    return (
        sf_user,
        user_role,
        opportunity,
        opportunity_line_item,
        opportunity_contact_role,
        account,
        contact,
        lead,
        campaign,
        campaign_member,
        product_2,
        pricebook_2,
        pricebook_entry,
        task,
        event,
    )
