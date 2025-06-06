"""Salesforce source helpers"""

from typing import Iterable

import pendulum
from dlt.common.typing import TDataItem
from simple_salesforce.api import Salesforce, SFType

from teamster.libraries.dlt.salesforce.pipeline.settings import IS_PRODUCTION


def get_records(
    sf: Salesforce,
    sobject: str,
    last_state: str | None = None,
    replication_key: str | None = None,
) -> Iterable[TDataItem]:
    """
    Retrieves records from Salesforce for a specified sObject.

    Args:
        sf (Salesforce): An instance of the Salesforce API client.
        sobject (str): The name of the sObject to retrieve records from.
        last_state (str, optional): The last known state for incremental loading.
            Defaults to None.
        replication_key (str, optional): The replication key for incremental loading.
            Defaults to None.

    Yields:
        Dict[TDataItem]: A dictionary representing a record from the Salesforce sObject.
    """

    s_object: SFType = getattr(sf, sobject)

    # Get all fields for the sobject
    desc = s_object.describe()

    # Salesforce returns compound fields as separate fields, so we need to filter them
    # out
    compound_fields = {
        f["compoundFieldName"]
        for f in desc["fields"]
        if f["compoundFieldName"] is not None
    } - {"Name"}

    # Salesforce returns datetime fields as timestamps, so we need to convert them
    date_fields = {
        f["name"] for f in desc["fields"] if f["type"] in ("datetime",) and f["name"]
    }

    # If no fields are specified, use all fields except compound fields
    fields = [f["name"] for f in desc["fields"] if f["name"] not in compound_fields]

    # Generate a predicate to filter records by the replication key
    predicate, order_by, n_records = "", "", 0

    if replication_key:
        if last_state:
            predicate = f"WHERE {replication_key} > {last_state}"

        order_by = f"ORDER BY {replication_key} ASC"

    # trunk-ignore(bandit/B608)
    query = f"SELECT {', '.join(fields)} FROM {sobject} {predicate} {order_by}"

    if not IS_PRODUCTION:
        query += " LIMIT 100"

    # Query all records in batches
    for page in getattr(sf.bulk, sobject).query_all(query, lazy_operation=True):
        for record in page:
            # Strip out the attributes field
            record.pop("attributes", None)

            for field in date_fields:
                # Convert Salesforce timestamps to ISO 8601
                if record.get(field):
                    record[field] = pendulum.from_timestamp(
                        record[field] / 1000,
                    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        yield from page

        n_records += len(page)
