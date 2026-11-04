import logging
import types

import pytest
from dagster import EnvVar, build_resources
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout
from tenacity import wait_none

from teamster.libraries.finalsite.api.resources import FinalsiteResource


def test_finalsite_resource():
    from teamster.code_locations.kippnewark import CODE_LOCATION

    with build_resources(
        {
            "finalsite": FinalsiteResource(
                server=CODE_LOCATION,
                credential_id=EnvVar("FINALSITE_CREDENTIAL_ID_KIPPNEWARK"),
                secret=EnvVar("FINALSITE_SECRET_KIPPNEWARK"),
            )
        }
    ) as resources:
        finalsite: FinalsiteResource = resources.finalsite

    assert finalsite is not None

    response = finalsite.list(path="contacts")

    print(response)


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        json_body: dict | None = None,
        *,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = text
        self.headers: dict[str, str] = headers or {}

    def json(self) -> dict:
        return self._json_body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"{self.status_code} Client Error", response=self)  # pyright: ignore[reportArgumentType]


def _build_offline_resource(request_fn) -> FinalsiteResource:
    """Instantiate the resource without the JWT setup_for_execution path."""
    finalsite = FinalsiteResource(server="test", credential_id="x", secret="x")

    object.__setattr__(finalsite, "_session", types.SimpleNamespace(request=request_fn))
    object.__setattr__(finalsite, "_log", logging.getLogger("test_finalsite"))

    return finalsite


def test_request_retries_on_403(monkeypatch: pytest.MonkeyPatch):
    """A shared-gateway 403 mid-pagination is transient and must be retried.

    All four districts' nightly contacts pulls fire simultaneously and share one
    egress IP; the Finalsite gateway returns a bare 403 once the concurrent load
    trips its per-source ceiling. A bounded backoff must retry rather than fail
    the whole pull.
    """
    # make tenacity backoff instant for the test
    monkeypatch.setattr(FinalsiteResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(403, text="403 Forbidden")
        return _FakeResponse(200, {"ok": True})

    finalsite = _build_offline_resource(request_fn)

    response = finalsite._request(method="GET", path="contacts", id=None)

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_does_not_retry_on_client_error(monkeypatch: pytest.MonkeyPatch):
    """A non-403/429 4xx is deterministic: raise immediately without retrying."""
    monkeypatch.setattr(FinalsiteResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(404, text="404 Not Found")

    finalsite = _build_offline_resource(request_fn)

    with pytest.raises(HTTPError):
        finalsite._request(method="GET", path="contacts", id=None)

    assert calls["n"] == 1


def test_request_exhausts_on_persistent_403(monkeypatch: pytest.MonkeyPatch):
    """A persistent 403 is retried up to the cap, then re-raises the HTTPError.

    Serialization (the concurrency pool) is the root-cause fix; this bounded
    retry is defense-in-depth, so a 403 that never clears must still surface as
    the original ``HTTPError`` and fail the run rather than hang.
    """
    monkeypatch.setattr(FinalsiteResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(403, text="403 Forbidden")

    finalsite = _build_offline_resource(request_fn)

    with pytest.raises(HTTPError):
        finalsite._request(method="GET", path="contacts", id=None)

    assert calls["n"] == 5


def test_request_retries_on_gateway_5xx(monkeypatch: pytest.MonkeyPatch):
    """A transient gateway 5xx mid-pagination is retried and recovers.

    The Finalsite gateway returns a 502 Bad Gateway (also 503/504) when its
    upstream briefly has no healthy backend. Like the shared-egress 403 and
    network faults, this is transient, so a bounded backoff must retry rather
    than fail the whole pull. Regression for prod run 7e56efa7.
    """
    monkeypatch.setattr(FinalsiteResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(502, text="502 Bad Gateway")
        return _FakeResponse(200, {"ok": True})

    finalsite = _build_offline_resource(request_fn)

    response = finalsite._request(method="GET", path="contacts", id=None)

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_exhausts_on_persistent_5xx(monkeypatch: pytest.MonkeyPatch):
    """A persistent 5xx is retried up to the cap, then re-raises the HTTPError.

    A gateway fault that never clears must still surface as the original
    ``HTTPError`` and fail the run rather than retry unbounded.
    """
    monkeypatch.setattr(FinalsiteResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(503, text="503 Service Unavailable")

    finalsite = _build_offline_resource(request_fn)

    with pytest.raises(HTTPError):
        finalsite._request(method="GET", path="contacts", id=None)

    assert calls["n"] == 5


def test_request_retries_on_network_faults(monkeypatch: pytest.MonkeyPatch):
    """A connect/read timeout or connection error is retried.

    A full pull makes hundreds of sequential requests, so a single network blip
    must not fail the whole run. Raising max_runtime makes a hung socket costly,
    so requests carry a timeout; the resulting ``Timeout`` is retried like any
    transient network fault.
    """
    monkeypatch.setattr(FinalsiteResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] == 1:
            raise Timeout("read timed out")
        if calls["n"] == 2:
            raise RequestsConnectionError("connection reset")
        return _FakeResponse(200, {"ok": True})

    finalsite = _build_offline_resource(request_fn)

    response = finalsite._request(method="GET", path="contacts", id=None)

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_handles_429_retry_after(monkeypatch: pytest.MonkeyPatch):
    """A 429 is handled in-band via ``Retry-After`` (not the tenacity backoff).

    Guards that the new 403/network retry decorator did not break the existing
    sleep-then-retry behavior for rate limits.
    """
    monkeypatch.setattr(FinalsiteResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 2:
            return _FakeResponse(429, text="rate limited", headers={"Retry-After": "0"})
        return _FakeResponse(200, {"ok": True})

    finalsite = _build_offline_resource(request_fn)

    response = finalsite._request(method="GET", path="contacts", id=None)

    assert response.status_code == 200
    assert calls["n"] == 2
