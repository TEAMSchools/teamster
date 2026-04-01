from collections.abc import Callable, Iterator
from typing import Any

from requests import Response


def paginate_cursor(
    fetch_page: Callable[[dict], Response],
    extract_records: Callable[[Response], list[dict[str, Any]]],
    extract_cursor: Callable[[Response], str | None],
    page_params: dict | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Cursor-based pagination. Stops when extract_cursor returns None.

    Args:
        fetch_page: Callable that accepts params dict and returns a Response.
        extract_records: Callable that extracts a list of records from a Response.
        extract_cursor: Callable that extracts the next cursor from a Response,
            or None when there are no more pages.
        page_params: Optional initial query parameters to include in every request.

    Yields:
        Lists of record dicts, one list per page.
    """
    params = dict(page_params) if page_params else {}

    while True:
        response = fetch_page(params)
        records = extract_records(response)
        yield records

        cursor = extract_cursor(response)
        if cursor is None:
            break
        params["page[after]"] = cursor


def paginate_offset(
    fetch_page: Callable[[dict], Response],
    extract_records: Callable[[Response], list[dict[str, Any]]],
    page_size: int,
    start: int = 0,
    offset_param: str = "offset",
    limit_param: str = "limit",
    is_last_page: Callable[[Response], bool] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Offset-based pagination. Stops when records < page_size or is_last_page.

    Args:
        fetch_page: Callable that accepts params dict and returns a Response.
        extract_records: Callable that extracts a list of records from a Response.
        page_size: Number of records per page; also the stop threshold.
        start: Initial offset value. Defaults to 0.
        offset_param: Query parameter name for the offset. Defaults to "offset".
        limit_param: Query parameter name for the page size. Defaults to "limit".
        is_last_page: Optional callable that returns True when the response
            indicates no further pages exist.

    Yields:
        Lists of record dicts, one list per page.
    """
    offset = start

    while True:
        params = {offset_param: offset, limit_param: page_size}
        response = fetch_page(params)
        records = extract_records(response)
        yield records

        if is_last_page is not None:
            if is_last_page(response):
                break
        elif len(records) < page_size:
            break
        offset += page_size


def paginate_page(
    fetch_page: Callable[[dict], Response],
    extract_records: Callable[[Response], list[dict[str, Any]]],
    page_size: int,
    start: int = 1,
    page_param: str = "page",
    size_param: str = "pagesize",
) -> Iterator[list[dict[str, Any]]]:
    """Page-number pagination. Stops when records empty or < page_size.

    Args:
        fetch_page: Callable that accepts params dict and returns a Response.
        extract_records: Callable that extracts a list of records from a Response.
        page_size: Number of records per page; also the stop threshold.
        start: Initial page number. Defaults to 1.
        page_param: Query parameter name for the page number. Defaults to "page".
        size_param: Query parameter name for the page size. Defaults to "pagesize".

    Yields:
        Lists of record dicts, one list per page.
    """
    page = start

    while True:
        params = {page_param: page, size_param: page_size}
        response = fetch_page(params)
        records = extract_records(response)
        yield records

        if len(records) == 0 or len(records) < page_size:
            break
        page += 1
