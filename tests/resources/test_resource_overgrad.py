"""Offline pagination tests for ``OvergradResource`` (no live API calls)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

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
