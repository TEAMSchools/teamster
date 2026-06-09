import logging
import types

import pytest
from requests.exceptions import HTTPError, JSONDecodeError, ReadTimeout
from tenacity import wait_none

from teamster.libraries.coupa.resources import CoupaError, CoupaResource


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        json_body,
        *,
        text: str = "",
        json_raises: bool = False,
    ) -> None:
        self.status_code = status_code
        self._json_body = json_body
        self.text = text
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise JSONDecodeError("Expecting value", "", 0)

        return self._json_body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"{self.status_code} Server Error", response=self)  # pyright: ignore[reportArgumentType]


def _build_offline_resource(request_fn) -> CoupaResource:
    """Instantiate the resource without the network setup_for_execution path."""
    coupa = CoupaResource(
        instance_url="example.test", client_id="x", client_secret="x", scope=["x"]
    )

    object.__setattr__(coupa, "_session", types.SimpleNamespace(request=request_fn))
    object.__setattr__(coupa, "_log", logging.getLogger("test_coupa"))
    object.__setattr__(coupa, "_service_root", "https://example.test")

    return coupa


def test_request_retries_on_read_timeout(monkeypatch: pytest.MonkeyPatch):
    """A ``ReadTimeout`` is transient and must be retried.

    Regression: ``CoupaResource`` had no retry, so a single read timeout (the
    actual 2026-06 prod failure) failed the step immediately.
    """
    monkeypatch.setattr(CoupaResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ReadTimeout("Read timed out. (read timeout=30)")
        return _FakeResponse(200, [{"ok": True}])

    coupa = _build_offline_resource(request_fn)

    response = coupa._request(method="GET", resource="users", id=None)

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_retries_on_server_error(monkeypatch: pytest.MonkeyPatch):
    """A 5xx response is transient and must be retried."""
    monkeypatch.setattr(CoupaResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(500, {}, text="500 Internal Server Error")
        return _FakeResponse(200, [{"ok": True}])

    coupa = _build_offline_resource(request_fn)

    response = coupa._request(method="GET", resource="users", id=None)

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_does_not_retry_on_client_error(monkeypatch: pytest.MonkeyPatch):
    """A non-429 4xx is deterministic: raise CoupaError without retrying."""
    monkeypatch.setattr(CoupaResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(400, {"error": "Bad Request"})

    coupa = _build_offline_resource(request_fn)

    with pytest.raises(CoupaError):
        coupa._request(method="GET", resource="users", id=None)

    assert calls["n"] == 1
