"""Offline retry tests for ``GrowResource``.

Kept separate from ``test_resource_grow.py``, whose tests hit the live Grow API.
"""

import logging
import types

import pytest
from requests.exceptions import HTTPError
from tenacity import wait_none

from teamster.libraries.level_data.grow.resources import (
    GrowAPIError,
    GrowResource,
    GrowServerError,
)


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def json(self) -> dict:
        return {"ok": True}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"{self.status_code} Server Error", response=self)  # pyright: ignore[reportArgumentType]


def _build_offline_resource(request_fn) -> GrowResource:
    """Instantiate the resource without the network setup_for_execution path."""
    grow = GrowResource(client_id="x", client_secret="x", district_id="x")

    object.__setattr__(grow, "_session", types.SimpleNamespace(request=request_fn))
    object.__setattr__(grow, "_log", logging.getLogger("test_grow"))

    return grow


def test_put_retries_on_server_error(monkeypatch: pytest.MonkeyPatch):
    """A 5xx on a PUT is a transient gateway failure and must be retried.

    Regression: a single 502 on a user update failed permanently, recorded an
    entry in the ``zero_api_errors`` check, and fired a WARN alert for work the
    next daily sync would have redone anyway.
    """
    # make tenacity backoff instant for the test
    monkeypatch.setattr(GrowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1

        if calls["n"] < 3:
            return _FakeResponse(502, "502 Server Error")

        return _FakeResponse(200)

    grow = _build_offline_resource(request_fn)

    assert grow.put("users", "abc", json={"name": "x"}) == {"ok": True}
    assert calls["n"] == 3


def test_post_does_not_retry_on_server_error(monkeypatch: pytest.MonkeyPatch):
    """A 5xx on a POST is not retried: the create may have landed server-side."""
    monkeypatch.setattr(GrowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1

        return _FakeResponse(502, "502 Server Error")

    grow = _build_offline_resource(request_fn)

    with pytest.raises(GrowAPIError) as excinfo:
        grow.post("users", json={"name": "x"})

    assert not isinstance(excinfo.value, GrowServerError)
    assert calls["n"] == 1


def test_client_error_does_not_retry(monkeypatch: pytest.MonkeyPatch):
    """A 4xx is deterministic: surface it to the asset's error list immediately."""
    monkeypatch.setattr(GrowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1

        return _FakeResponse(400, '{"message":"ValidationError"}')

    grow = _build_offline_resource(request_fn)

    with pytest.raises(GrowAPIError):
        grow.put("users", "abc", json={"name": "x"})

    assert calls["n"] == 1


def test_server_error_exhausts_retries_as_grow_api_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """A persistent 5xx still lands in the asset's error list after retries.

    ``GrowServerError`` subclasses ``GrowAPIError``, so ``grow_user_sync``
    catches it without a change to the asset.
    """
    monkeypatch.setattr(GrowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1

        return _FakeResponse(502, "502 Server Error")

    grow = _build_offline_resource(request_fn)

    with pytest.raises(GrowAPIError):
        grow.delete("users", "abc")

    assert calls["n"] == 3
