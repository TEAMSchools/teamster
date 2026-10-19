"""Offline pagination tests for ``OvergradResource`` (no live API calls)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import ReadTimeout
from tenacity import wait_none

from teamster.libraries.overgrad import resources as overgrad_resources
from teamster.libraries.overgrad.resources import OvergradResource


class _FakeResponse:
    def __init__(self, page: int, total_pages: int):
        self._page = page
        self._total_pages = total_pages

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {
            "object": "list",
            "total_pages": self._total_pages,
            "current_page": self._page,
            "data": [{"id": self._page}],
        }


def test_list_logs_once_per_call(monkeypatch):
    monkeypatch.setattr(overgrad_resources.time, "sleep", lambda _: None)

    resource = OvergradResource(api_key="test")
    log = MagicMock()
    object.__setattr__(resource, "_log", log)

    def fake_request(params, **_):
        return _FakeResponse(page=params["page"], total_pages=3)

    object.__setattr__(resource, "_session", SimpleNamespace(request=fake_request))

    data = resource.list(path="admissions")

    assert [d["id"] for d in data] == [1, 2, 3]
    assert len(log.method_calls) == 1
    log.info.assert_called_once()


@pytest.mark.parametrize(
    "error", [RequestsConnectionError("Remote end closed"), ReadTimeout("timed out")]
)
def test_request_retries_transient_network_errors(monkeypatch, error):
    monkeypatch.setattr(OvergradResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    resource = OvergradResource(api_key="test")
    calls = []

    def fake_request(**_):
        calls.append(1)
        if len(calls) == 1:
            raise error
        return _FakeResponse(page=1, total_pages=1)

    object.__setattr__(resource, "_session", SimpleNamespace(request=fake_request))

    resource._request(method="GET", url="https://example.test")

    assert len(calls) == 2
