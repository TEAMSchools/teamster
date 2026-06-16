import logging
import types

import pytest
from dagster import EnvVar, build_resources
from requests.exceptions import HTTPError, JSONDecodeError, ReadTimeout
from tenacity import wait_none

from teamster.libraries.knowbe4.resources import KnowBe4Error, KnowBe4Resource


def test_knowbe4_resource():
    with build_resources(
        {
            "knowbe4": KnowBe4Resource(
                api_key=EnvVar("KNOWBE4_API_KEY"), server="us", page_size=500
            )
        }
    ) as resources:
        knowbe4: KnowBe4Resource = resources.knowbe4

    assert knowbe4 is not None


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


def _build_offline_resource(request_fn) -> KnowBe4Resource:
    """Instantiate the resource without the network setup_for_execution path."""
    knowbe4 = KnowBe4Resource(api_key="x", server="us")

    object.__setattr__(knowbe4, "_session", types.SimpleNamespace(request=request_fn))
    object.__setattr__(knowbe4, "_log", logging.getLogger("test_knowbe4"))
    object.__setattr__(knowbe4, "_service_root", "https://us.api.knowbe4.com")

    return knowbe4


def test_request_retries_on_server_error(monkeypatch: pytest.MonkeyPatch):
    """A 5xx response is transient and must be retried.

    Regression: ``KnowBe4Resource`` had no retry, so a single 500 (the actual
    2026-06 prod failure on ``training/enrollments``) failed the step
    immediately.
    """
    monkeypatch.setattr(KnowBe4Resource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(500, {}, text="500 Internal Server Error")
        return _FakeResponse(200, [{"ok": True}])

    knowbe4 = _build_offline_resource(request_fn)

    response = knowbe4._request(method="GET", resource="training/enrollments", id=None)

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_retries_on_read_timeout(monkeypatch: pytest.MonkeyPatch):
    """A ``ReadTimeout`` is transient and must be retried."""
    monkeypatch.setattr(KnowBe4Resource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ReadTimeout("Read timed out")
        return _FakeResponse(200, [{"ok": True}])

    knowbe4 = _build_offline_resource(request_fn)

    response = knowbe4._request(method="GET", resource="training/enrollments", id=None)

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_does_not_retry_on_client_error(monkeypatch: pytest.MonkeyPatch):
    """A non-429 4xx is deterministic: raise KnowBe4Error without retrying."""
    monkeypatch.setattr(KnowBe4Resource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(400, {"error": "Bad Request"})

    knowbe4 = _build_offline_resource(request_fn)

    with pytest.raises(KnowBe4Error):
        knowbe4._request(method="GET", resource="training/enrollments", id=None)

    assert calls["n"] == 1
