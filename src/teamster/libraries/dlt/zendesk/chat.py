"""
Defines all the sources and resources needed for ZendeskChat
"""

from typing import Iterable, Iterator, Optional

import dlt
from dlt.common.time import ensure_pendulum_datetime
from dlt.common.typing import TAnyDateTime, TDataItems
from dlt.sources import DltResource

from teamster.libraries.dlt.zendesk.credentials import ZendeskCredentialsOAuth
from teamster.libraries.dlt.zendesk.helpers import PaginationType, ZendeskAPIClient
from teamster.libraries.dlt.zendesk.settings import DEFAULT_START_DATE


@dlt.source(max_table_nesting=2)
def zendesk_chat(
    credentials: ZendeskCredentialsOAuth = dlt.secrets.value,
    start_date: TAnyDateTime = DEFAULT_START_DATE,
    end_date: Optional[TAnyDateTime] = None,
) -> Iterable[DltResource]:
    """
    Retrieves data from Zendesk Chat for chat interactions.

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
        DltResource: Data resources from Zendesk Chat.
    """

    # Authenticate
    zendesk_client = ZendeskAPIClient(credentials, url_prefix="https://www.zopim.com")
    start_date_obj = ensure_pendulum_datetime(start_date)
    end_date_obj = ensure_pendulum_datetime(end_date) if end_date else None

    yield dlt.resource(chats_table_resource, name="chats", write_disposition="merge")(
        zendesk_client,
        dlt.sources.incremental[str](
            "update_timestamp|updated_timestamp",
            initial_value=start_date_obj.isoformat(),
            end_value=end_date_obj.isoformat() if end_date_obj else None,
            allow_external_schedulers=True,
        ),
    )


def chats_table_resource(
    zendesk_client: ZendeskAPIClient,
    update_timestamp: dlt.sources.incremental[str],
) -> Iterator[TDataItems]:
    """
    Resource for Chats

    Args:
        zendesk_client: The Zendesk API client instance, used to make calls to Zendesk API.
        update_timestamp: Incremental source specifying the timestamp for incremental loading.

    Yields:
        dict: A dictionary representing each row of data.
    """
    chat_pages = zendesk_client.get_pages(
        "/api/v2/incremental/chats",
        "chats",
        PaginationType.START_TIME,
        params={
            "start_time": ensure_pendulum_datetime(
                update_timestamp.last_value
            ).int_timestamp,
            "fields": "chats(*)",
        },
    )
    for page in chat_pages:
        yield page

        if update_timestamp.end_out_of_range:
            return
