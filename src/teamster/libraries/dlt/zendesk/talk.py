"""
Defines all the sources and resources needed for ZendeskTalk
"""

from typing import Iterable, Iterator, Optional

import dlt
from dlt.common.time import ensure_pendulum_datetime
from dlt.common.typing import TAnyDateTime, TDataItem
from dlt.sources import DltResource

from teamster.libraries.dlt.zendesk.credentials import TZendeskCredentials
from teamster.libraries.dlt.zendesk.helpers import PaginationType, ZendeskAPIClient
from teamster.libraries.dlt.zendesk.settings import (
    DEFAULT_START_DATE,
    INCREMENTAL_TALK_ENDPOINTS,
    TALK_ENDPOINTS,
)


@dlt.source(max_table_nesting=2)
def zendesk_talk(
    credentials: TZendeskCredentials = dlt.secrets.value,
    start_date: Optional[TAnyDateTime] = DEFAULT_START_DATE,
    end_date: Optional[TAnyDateTime] = None,
) -> Iterable[DltResource]:
    """
    Retrieves data from Zendesk Talk for phone calls and voicemails.

    `start_date` argument can be used on its own or together with `end_date`. When both are provided
    data is limited to items updated in that time range.
    The range is "half-open", meaning elements equal and higher than `start_date` and elements lower than `end_date` are included.
    All resources opt-in to use Airflow scheduler if run as Airflow task

    Args:
        credentials: The credentials for authentication. Defaults to the value in the `dlt.secrets` object.
        start_date: The start time of the range for which to load. Defaults to January 1st 2000.
        end_date: The end time of the range for which to load data.
            If end time is not provided, the incremental loading will be enabled and after initial run, only new data will be retrieved
    Yields:
        DltResource: Data resources from Zendesk Talk.
    """

    # use the credentials to authenticate with the ZendeskClient
    zendesk_client = ZendeskAPIClient(credentials)
    start_date_obj = ensure_pendulum_datetime(start_date)
    end_date_obj = ensure_pendulum_datetime(end_date) if end_date else None

    # regular endpoints
    for key, talk_endpoint, item_name, cursor_paginated in TALK_ENDPOINTS:
        yield dlt.resource(
            talk_resource(
                zendesk_client,
                key,
                item_name or talk_endpoint,
                PaginationType.CURSOR if cursor_paginated else PaginationType.OFFSET,
            ),
            name=key,
            write_disposition="replace",
        )

    # adding incremental endpoints
    for key, talk_incremental_endpoint in INCREMENTAL_TALK_ENDPOINTS.items():
        yield dlt.resource(
            talk_incremental_resource,
            name=f"{key}_incremental",
            primary_key="id",
            write_disposition="merge",
        )(
            zendesk_client=zendesk_client,
            talk_endpoint_name=key,
            talk_endpoint=talk_incremental_endpoint,
            updated_at=dlt.sources.incremental[str](
                "updated_at",
                initial_value=start_date_obj.isoformat(),
                end_value=end_date_obj.isoformat() if end_date_obj else None,
                allow_external_schedulers=True,
            ),
        )


def talk_resource(
    zendesk_client: ZendeskAPIClient,
    talk_endpoint_name: str,
    talk_endpoint: str,
    pagination_type: PaginationType,
) -> Iterator[TDataItem]:
    """
    Loads data from a Zendesk Talk endpoint.

    Args:
        zendesk_client: An instance of ZendeskAPIClient for making API calls to Zendesk Talk.
        talk_endpoint_name: The name of the talk_endpoint.
        talk_endpoint: The actual URL ending of the endpoint.
        pagination: Type of pagination type used by endpoint

    Yields:
        TDataItem: Dictionary containing the data from the endpoint.
    """
    # send query and process it
    yield from zendesk_client.get_pages(
        talk_endpoint, talk_endpoint_name, pagination_type
    )


def talk_incremental_resource(
    zendesk_client: ZendeskAPIClient,
    talk_endpoint_name: str,
    talk_endpoint: str,
    updated_at: dlt.sources.incremental[str],
) -> Iterator[TDataItem]:
    """
    Loads data from a Zendesk Talk endpoint with incremental loading.

    Args:
        zendesk_client: An instance of ZendeskAPIClient for making API calls to Zendesk Talk.
        talk_endpoint_name: The name of the talk_endpoint.
        talk_endpoint: The actual URL ending of the endpoint.
        updated_at: Source for the last updated timestamp.

    Yields:
        TDataItem: Dictionary containing the data from the endpoint.
    """
    # send the request and process it
    for page in zendesk_client.get_pages(
        talk_endpoint,
        talk_endpoint_name,
        PaginationType.START_TIME,
        params={
            "start_time": ensure_pendulum_datetime(updated_at.last_value).int_timestamp
        },
    ):
        yield page
        if updated_at.end_out_of_range:
            return
