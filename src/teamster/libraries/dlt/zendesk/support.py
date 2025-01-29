"""
Defines all the sources and resources needed for ZendeskSupport
"""

from itertools import chain
from typing import Iterable, Iterator

import dlt
from dlt.common import pendulum
from dlt.common.time import ensure_pendulum_datetime
from dlt.common.typing import TAnyDateTime, TDataItem
from dlt.sources import DltResource

from teamster.libraries.dlt.zendesk.api_helpers import (
    process_ticket,
    process_ticket_field,
)
from teamster.libraries.dlt.zendesk.credentials import TZendeskCredentials
from teamster.libraries.dlt.zendesk.helpers import PaginationType, ZendeskAPIClient
from teamster.libraries.dlt.zendesk.settings import (
    CUSTOM_FIELDS_STATE_KEY,
    DEFAULT_START_DATE,
    SUPPORT_ENDPOINTS,
    SUPPORT_EXTRA_ENDPOINTS,
)


@dlt.source(max_table_nesting=2)
def zendesk_support(
    credentials: TZendeskCredentials = dlt.secrets.value,
    load_all: bool = True,
    pivot_ticket_fields: bool = True,
    start_date: TAnyDateTime = DEFAULT_START_DATE,
    end_date: TAnyDateTime | None = None,
) -> Iterable[DltResource]:
    """
    Retrieves data from Zendesk Support for tickets, users, brands, organizations, and
    groups.

    `start_date` argument can be used on its own or together with `end_date`. When both
    are provided data is limited to items updated in that time range. The range is
    "half-open", meaning elements equal and higher than `start_date` and elements lower
    than `end_date` are included.
    All resources opt-in to use Airflow scheduler if run as Airflow task

    Args:
        credentials: The credentials for authentication. Defaults to the value in the
            `dlt.secrets` object.
        load_all: Whether to load extra resources for the API. Defaults to True.
        pivot_ticket_fields: Whether to pivot the custom fields in tickets. Defaults to
            True.
        start_date: The start time of the range for which to load. Defaults to January
            1st 2000.
        end_date: The end time of the range for which to load data.
            If end time is not provided, the incremental loading will be enabled and
            after initial run, only new data will be retrieved

    Returns:
        Sequence[DltResource]: Multiple dlt resources.
    """

    start_date_obj = ensure_pendulum_datetime(start_date)
    end_date_obj = ensure_pendulum_datetime(end_date) if end_date else None

    start_date_ts = start_date_obj.int_timestamp
    start_date_iso_str = start_date_obj.isoformat()
    end_date_ts: int | None = None
    end_date_iso_str: str | None = None

    if end_date_obj:
        end_date_ts = end_date_obj.int_timestamp
        end_date_iso_str = end_date_obj.isoformat()

    @dlt.resource(primary_key="id", write_disposition="append")
    def ticket_events(
        zendesk_client: ZendeskAPIClient,
        timestamp: dlt.sources.incremental[int] | None = None,
    ) -> Iterator[TDataItem]:
        if timestamp is None:
            timestamp = dlt.sources.incremental(
                cursor_path="timestamp",
                initial_value=start_date_ts,
                end_value=end_date_ts,
                allow_external_schedulers=True,
            )

        for page in zendesk_client.get_pages(
            endpoint="/api/v2/incremental/ticket_events.json",
            data_point_name="ticket_events",
            pagination=PaginationType.STREAM,
            params={"start_time": timestamp.last_value},
        ):
            yield page

            if timestamp.end_out_of_range:
                return

    @dlt.resource(
        name="tickets",
        primary_key="id",
        write_disposition="merge",
        columns={"tags": {"data_type": "json"}, "custom_fields": {"data_type": "json"}},
    )
    def ticket_table(
        zendesk_client: ZendeskAPIClient,
        pivot_fields: bool = True,
        updated_at: dlt.sources.incremental[pendulum.DateTime] | None = None,
    ) -> Iterator[TDataItem]:
        """
        Resource for tickets table. Uses DLT state to handle column renaming of custom
        fields to prevent changing the names of said columns.
        This resource uses pagination, loading and side loading to make API calls more
        efficient.

        Args:
            zendesk_client: The Zendesk API client instance, used to make calls to
                Zendesk API.
            pivot_fields: Indicates whether to pivot the custom fields in tickets.
                Defaults to True.
            per_page: The number of Ticket objects to load per page. Defaults to 1000.
            updated_at: Incremental source for the 'updated_at' column.
                Defaults to dlt.sources.incremental("updated_at",
                initial_value=start_date).

        Yields:
            TDataItem: Dictionary containing the ticket data.
        """

        if updated_at is None:
            updated_at = dlt.sources.incremental(
                cursor_path="updated_at",
                initial_value=start_date_obj,
                end_value=end_date_obj,
                allow_external_schedulers=True,
            )

        # grab the custom fields from dlt state if any
        if pivot_fields:
            load_ticket_fields_state(zendesk_client)

        fields_dict = dlt.current.source_state().setdefault(CUSTOM_FIELDS_STATE_KEY, {})

        # include_objects = ["users", "groups", "organisation", "brands"]
        for page in zendesk_client.get_pages(
            endpoint="/api/v2/incremental/tickets",
            data_point_name="tickets",
            pagination=PaginationType.STREAM,
            params={"start_time": updated_at.last_value.int_timestamp},
        ):
            yield [
                process_ticket(
                    ticket=ticket,
                    custom_fields=fields_dict,
                    pivot_custom_fields=pivot_fields,
                )
                for ticket in page
            ]

            # stop loading when using end_value and end is reached
            if updated_at.end_out_of_range:
                return

    @dlt.resource(
        name="ticket_metric_events", primary_key="id", write_disposition="append"
    )
    def ticket_metric_table(
        zendesk_client: ZendeskAPIClient,
        time: dlt.sources.incremental[str] | None = None,
    ) -> Iterator[TDataItem]:
        """
        Resource for ticket metric events table. Returns all the ticket metric events
        from the starting date, with the default starting date being January 1st of the
        current year.

        Args:
            zendesk_client: The Zendesk API client instance, used to make calls to
                Zendesk API.
            time: Incremental source for the 'time' column,
                indicating the starting date for retrieving ticket metric events.
                Defaults to dlt.sources.incremental("time",
                initial_value=start_date_iso_str).

        Yields:
            TDataItem: Dictionary containing the ticket metric event data.
        """

        if time is None:
            time = dlt.sources.incremental(
                cursor_path="time",
                initial_value=start_date_iso_str,
                end_value=end_date_iso_str,
                allow_external_schedulers=True,
            )

        # "https://example.zendesk.com/api/v2/incremental/ticket_metric_events?start_time=1332034771"
        for page in zendesk_client.get_pages(
            endpoint="/api/v2/incremental/ticket_metric_events",
            data_point_name="ticket_metric_events",
            pagination=PaginationType.CURSOR,
            params={
                "start_time": ensure_pendulum_datetime(time.last_value).int_timestamp,
            },
        ):
            yield page

            if time.end_out_of_range:
                return

    def ticket_fields_table(zendesk_client: ZendeskAPIClient) -> Iterator[TDataItem]:
        """
        Loads ticket fields data from Zendesk API.

        Args:
            zendesk_client: The Zendesk API client instance, used to make calls to
            Zendesk API.

        Yields:
            TDataItem: Dictionary containing the ticket fields data.
        """
        # get dlt state
        ticket_custom_fields = dlt.current.source_state().setdefault(
            CUSTOM_FIELDS_STATE_KEY, {}
        )

        # get all custom fields and update state if needed, otherwise just load dicts
        # into tables
        all_fields = list(
            chain.from_iterable(
                zendesk_client.get_pages(
                    endpoint="/api/v2/ticket_fields.json",
                    data_point_name="ticket_fields",
                    pagination=PaginationType.OFFSET,
                )
            )
        )

        # all_fields = zendesk_client.ticket_fields()
        for field in all_fields:
            yield process_ticket_field(
                field=field, custom_fields_state=ticket_custom_fields
            )

    def load_ticket_fields_state(zendesk_client: ZendeskAPIClient) -> None:
        for _ in ticket_fields_table(zendesk_client):
            pass

    ticket_fields_resource = dlt.resource(
        name="ticket_fields", write_disposition="replace"
    )(ticket_fields_table)

    # Authenticate
    zendesk_client = ZendeskAPIClient(credentials)

    # loading base tables
    resource_list = [
        ticket_fields_resource(zendesk_client=zendesk_client),
        ticket_events(zendesk_client=zendesk_client),
        ticket_table(zendesk_client=zendesk_client, pivot_fields=pivot_ticket_fields),
        ticket_metric_table(zendesk_client=zendesk_client),
    ]

    # other tables to be loaded
    resources_to_be_loaded = list(SUPPORT_ENDPOINTS)  # make a copy

    if load_all:
        resources_to_be_loaded.extend(SUPPORT_EXTRA_ENDPOINTS)

    for resource, endpoint_url, data_key, cursor_paginated in resources_to_be_loaded:
        resource_list.append(
            dlt.resource(
                support_resource(
                    zendesk_client=zendesk_client,
                    endpoint_url=endpoint_url,
                    data_key=data_key or resource,
                    cursor_paginated=cursor_paginated,
                ),
                name=resource,
                write_disposition="replace",
            )
        )

    return resource_list


def support_resource(
    zendesk_client: ZendeskAPIClient,
    endpoint_url: str,
    data_key: str,
    cursor_paginated: bool,
) -> Iterator[TDataItem]:
    """
    Basic loader for most endpoints offered by Zenpy. Supports pagination. Expects to
    be called as a DLT Resource.

    Args:
        zendesk_client: The Zendesk API client instance, used to make calls to Zendesk
            API.
        resource: The Zenpy endpoint to retrieve data from, usually directly linked to
            a Zendesk API endpoint.
        cursor_paginated: Tells to use CURSOR pagination or OFFSET/no pagination

    Yields:
        TDataItem: Dictionary containing the resource data.
    """

    pages = zendesk_client.get_pages(
        endpoint=endpoint_url,
        data_point_name=data_key,
        pagination=PaginationType.CURSOR if cursor_paginated else PaginationType.OFFSET,
    )

    yield from pages
