import json
import logging
import pathlib
import traceback

import pytest
from requests import PreparedRequest, Response
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError

from teamster.libraries.deanslist.resources import (
    DeansListResource,
    load_deanslist_config,
    redact_api_keys,
)

# synthetic stand-in for a per-school key; low entropy so no secret scanner bites
PLACEHOLDER_KEY = "placeholder-key-for-school-121"


class _FakeSession:
    """Renders the query string exactly as ``requests`` would, offline.

    The rendered URL is what carries the ``apikey`` parameter into
    ``response.url`` and into the message ``raise_for_status()`` builds, so the
    test has to reproduce it faithfully to prove the leak is closed.
    """

    def __init__(self, status_codes: list[int]) -> None:
        self._status_codes = list(status_codes)
        self.sent_params: list[dict] = []

    def request(
        self, method: str, url: str, params: dict, timeout: float, **kwargs
    ) -> Response:
        self.sent_params.append(dict(params))

        prepared = PreparedRequest()
        prepared.prepare(method=method, url=url, params=params)

        response = Response()

        response.status_code = self._status_codes.pop(0)
        response.reason = "Internal Server Error"
        response.url = prepared.url  # pyright: ignore[reportAttributeAccessIssue]
        response.request = prepared

        return response


class _FakeConnectionErrorSession:
    """Fails in transport, with the rendered URL in the message.

    Mirrors urllib3, whose `MaxRetryError` embeds `url: <path>?apikey=<key>` —
    the reason a transport failure leaks the same credential a 4xx does.
    """

    def __init__(self) -> None:
        self.sent_params: list[dict] = []

    def request(
        self, method: str, url: str, params: dict, timeout: float, **kwargs
    ) -> Response:
        self.sent_params.append(dict(params))

        prepared = PreparedRequest()
        prepared.prepare(method=method, url=url, params=params)

        error = RequestsConnectionError(
            f"HTTPSConnectionPool(host='kippnj.deanslistsoftware.com', port=443): "
            f"Max retries exceeded with url: {prepared.url} "
            "(Caused by NewConnectionError('Connection refused'))"
        )
        error.request = prepared

        raise error


def _build_offline_resource(session, logger_name: str) -> DeansListResource:
    """Instantiate the resource without the secret-volume setup path."""
    resource = DeansListResource(api_key_dir="/etc/deanslist")

    object.__setattr__(resource, "_api_key_map", {121: PLACEHOLDER_KEY})
    object.__setattr__(resource, "_session", session)
    object.__setattr__(resource, "_log", logging.getLogger(logger_name))

    return resource


def test_load_deanslist_config(tmp_path: pathlib.Path):
    (tmp_path / "subdomain").write_text("kippnj\n")
    (tmp_path / "121").write_text("key-121\n")
    (tmp_path / "122").write_text("key-122")
    # projected-secret volumes stage data behind dot-prefixed entries
    (tmp_path / "..data").mkdir()
    (tmp_path / ".hidden").write_text("ignore-me")

    subdomain, api_key_map = load_deanslist_config(tmp_path)

    assert subdomain == "kippnj"
    assert api_key_map == {121: "key-121", 122: "key-122"}


def test_request_missing_school_key_raises_named_error():
    resource = DeansListResource(api_key_dir="/etc/deanslist")
    object.__setattr__(resource, "_api_key_map", {121: "key-121"})
    object.__setattr__(resource, "_log", logging.getLogger("test"))

    # school_id 999 has no key file synced — the guard must raise before any
    # network call, naming the school id and the mount
    with pytest.raises(KeyError, match="No DeansList API key for school_id 999"):
        resource._request(method="GET", url="https://x/api", school_id=999, params={})


def test_redact_api_keys():
    """Every rendering the key can reach a log through must come back masked."""
    # the query form `raise_for_status()` embeds, with the value percent-encoded
    # by requests so a literal match on the raw key would miss it
    assert (
        redact_api_keys("500 Server Error: for url: https://x/api?a=1&apikey=a%2Bb%2F")
        == "500 Server Error: for url: https://x/api?a=1&apikey=***"
    )

    # the query form is masked even when the key value is unknown to the caller
    assert redact_api_keys("?APIKEY=abc123&page=2") == "?apikey=***&page=2"

    # a params dict repr uses no `apikey=` form, so the literal value is masked
    assert (
        redact_api_keys("PARAMS:\t{'apikey': 'abc123'}", api_keys=["abc123"])
        == "PARAMS:\t{'apikey': '***'}"
    )

    # every school's key is masked, not just the one for the failing request
    assert redact_api_keys("a-b", api_keys=["a", "b"]) == "***-***"

    # text with no key is untouched
    assert redact_api_keys("GET:\thttps://x/api/v1/students") == (
        "GET:\thttps://x/api/v1/students"
    )


def test_request_error_never_logs_or_raises_the_api_key(
    caplog: pytest.LogCaptureFixture,
):
    """A 4xx/5xx must not put the school's API key into the Dagster event log.

    The key is sent as an `apikey` query parameter, so `raise_for_status()`
    builds its message around the fully rendered URL. Logging that exception (or
    letting it propagate for Dagster to serialize) persisted a live credential
    into the run log on every DeansList error.
    """
    session = _FakeSession(status_codes=[500])
    resource = _build_offline_resource(session, "test_deanslist_error")
    params = {"IncludeInactive": "Y"}

    with caplog.at_level(logging.INFO, logger="test_deanslist_error"):
        with pytest.raises(HTTPError) as exc_info:
            resource._request(
                method="GET",
                url="https://kippnj.deanslistsoftware.com/api/v1/students",
                school_id=121,
                params=params,
            )

    # the key really was sent on the wire — the redaction is a logging change,
    # not a protocol change
    assert session.sent_params == [{"IncludeInactive": "Y", "apikey": PLACEHOLDER_KEY}]

    # ...and it reaches neither the log, the raised message, nor the traceback
    # Dagster serializes (`raise ... from None` suppresses the original)
    rendered_traceback = "".join(traceback.format_exception(exc_info.value))

    assert PLACEHOLDER_KEY not in caplog.text
    assert PLACEHOLDER_KEY not in str(exc_info.value)
    assert PLACEHOLDER_KEY not in rendered_traceback

    # what survives is still enough to debug: the INFO request line names the
    # endpoint and school, and the raised message (which Dagster logs on step
    # failure) keeps the status and a masked URL with the non-secret params.
    # Only that one record: no duplicate ERROR from inside `_request`.
    assert "/api/v1/students" in caplog.text
    assert "SCHOOL_ID:\t121" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert "500 Server Error" in str(exc_info.value)
    assert "IncludeInactive=Y" in str(exc_info.value)
    assert "apikey=***" in str(exc_info.value)

    # the same exception type still propagates, with the response attached
    assert exc_info.value.response is not None
    assert exc_info.value.response.status_code == 500

    # `__context__` must be None, not merely suppressed. `raise ... from None`
    # sets `__suppress_context__`, which `traceback` honors — but the original
    # exception object, whose message holds the unredacted URL, stays reachable
    # on `__context__` for any consumer that walks the chain unconditionally.
    # Raising outside the `except` block is what actually drops it.
    assert exc_info.value.__context__ is None


def test_transport_error_never_raises_the_api_key(caplog: pytest.LogCaptureFixture):
    """A connection failure must not leak the key either.

    `raise_for_status()` is never reached when the request dies in transport, and
    urllib3 renders the full URL — query string included — into the
    `ConnectionError` message, which then propagates uncaught for Dagster to
    serialize. Same credential, same surface, different trigger.
    """
    session = _FakeConnectionErrorSession()
    resource = _build_offline_resource(session, "test_deanslist_transport")

    with caplog.at_level(logging.INFO, logger="test_deanslist_transport"):
        with pytest.raises(RequestsConnectionError) as exc_info:
            resource._request(
                method="GET",
                url="https://kippnj.deanslistsoftware.com/api/v1/students",
                school_id=121,
                params={"IncludeInactive": "Y"},
            )

    rendered_traceback = "".join(traceback.format_exception(exc_info.value))

    assert PLACEHOLDER_KEY not in caplog.text
    assert PLACEHOLDER_KEY not in str(exc_info.value)
    assert PLACEHOLDER_KEY not in rendered_traceback
    assert exc_info.value.__context__ is None

    # the subclass is preserved so the documented retry predicate still matches
    assert isinstance(exc_info.value, RequestsConnectionError)

    # and the diagnostic survives
    assert "apikey=***" in str(exc_info.value)
    assert "/api/v1/students" in str(exc_info.value)


def test_request_does_not_retain_the_api_key_in_the_caller_params(
    caplog: pytest.LogCaptureFixture,
):
    """A failed request must not leave the key in the caller's params dict.

    The asset factories build one params dict per asset and reuse it for every
    partition, so a key retained after a failure was logged verbatim by the next
    partition's request line.
    """
    session = _FakeSession(status_codes=[500, 200])
    resource = _build_offline_resource(session, "test_deanslist_retention")
    params = {"IncludeInactive": "Y"}

    with caplog.at_level(logging.INFO, logger="test_deanslist_retention"):
        with pytest.raises(HTTPError):
            resource._request(
                method="GET",
                url="https://kippnj.deanslistsoftware.com/api/v1/students",
                school_id=121,
                params=params,
            )

        assert params == {"IncludeInactive": "Y"}
        caplog.clear()

        # the next partition reuses the same dict
        response = resource._request(
            method="GET",
            url="https://kippnj.deanslistsoftware.com/api/v1/students",
            school_id=121,
            params=params,
        )

    assert response.status_code == 200
    assert PLACEHOLDER_KEY not in caplog.text
    assert params == {"IncludeInactive": "Y"}


class _FakePageSession:
    """Serves a single-page ``list()`` response offline."""

    def __init__(self) -> None:
        self.sent_params: list[dict] = []

    def request(
        self, method: str, url: str, params: dict, timeout: float, **kwargs
    ) -> Response:
        self.sent_params.append(dict(params))

        response = Response()

        response.status_code = 200
        response._content = json.dumps(
            {"total_count": 1, "total_pages": 1, "data": [{"id": 1}]}
        ).encode()

        return response


def test_list_does_not_add_paging_params_to_the_caller_params(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    """``list()`` sends page_size/page from a copy, like ``_request`` does the key.

    The paginated asset reuses one params dict across partitions, so paging
    params written into it would leak into every later request.
    """
    # list() opens its data file under the working directory
    monkeypatch.chdir(tmp_path)
    (tmp_path / "env" / "deanslist" / "behavior" / "2024-07-01" / "121").mkdir(
        parents=True
    )

    session = _FakePageSession()
    resource = _build_offline_resource(session, "test_deanslist_list")
    object.__setattr__(resource, "_base_url", "https://x/api")
    params = {"UpdatedSince": "2024-07-01"}

    total_count, data = resource.list(
        api_version="v1", endpoint="behavior", school_id=121, params=params
    )

    assert (total_count, data) == (1, [{"id": 1}])
    assert params == {"UpdatedSince": "2024-07-01"}
    assert session.sent_params == [
        {
            "UpdatedSince": "2024-07-01",
            "page_size": 250000,
            "page": 1,
            "apikey": PLACEHOLDER_KEY,
        }
    ]
