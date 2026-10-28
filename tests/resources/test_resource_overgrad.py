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


def test_list_passes_params_through(monkeypatch):
    monkeypatch.setattr(overgrad_resources.time, "sleep", lambda _: None)

    resource = OvergradResource(api_key="test")
    object.__setattr__(resource, "_log", MagicMock())

    seen = []

    def fake_request(params, **_):
        seen.append(dict(params))
        return _FakeResponse(page=params["page"], total_pages=2)

    object.__setattr__(resource, "_session", SimpleNamespace(request=fake_request))

    caller_params = {"updated_after": "2026-10-28T18:00:00.000Z"}
    resource.list(path="admissions", params=caller_params)

    assert [p["updated_after"] for p in seen] == ["2026-10-28T18:00:00.000Z"] * 2
    assert [p["page"] for p in seen] == [1, 2]
    assert all(p["limit"] == resource.page_limit for p in seen)
    assert caller_params == {"updated_after": "2026-10-28T18:00:00.000Z"}


def test_list_accepts_params_none(monkeypatch):
    monkeypatch.setattr(overgrad_resources.time, "sleep", lambda _: None)

    resource = OvergradResource(api_key="test")
    object.__setattr__(resource, "_log", MagicMock())

    def fake_request(params, **_):
        return _FakeResponse(page=params["page"], total_pages=1)

    object.__setattr__(resource, "_session", SimpleNamespace(request=fake_request))

    assert resource.list(path="admissions", params=None) == [{"id": 1}]


def test_list_stops_on_empty_result(monkeypatch):
    monkeypatch.setattr(overgrad_resources.time, "sleep", lambda _: None)

    resource = OvergradResource(api_key="test")
    object.__setattr__(resource, "_log", MagicMock())

    pages = []

    def fake_request(params, **_):
        pages.append(params["page"])
        if len(pages) > 1:
            raise AssertionError("requested a page past an empty result")
        # Overgrad reports total_pages 0, not 1, when nothing matches
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"total_pages": 0, "current_page": 1, "data": []},
        )

    object.__setattr__(resource, "_session", SimpleNamespace(request=fake_request))

    assert resource.list(path="followings") == []
    assert pages == [1]


def _ts(second: int) -> str:
    return f"2026-10-28T10:00:{second:02d}.000Z"


class _FakeApi:
    """Serves records the way Overgrad does: sorted by `updated_at` ascending,
    filtered by an inclusive `updated_after`, paged by `limit` and `page`."""

    def __init__(self, records: list[dict], after_first_request=None):
        self.records = records
        self.after_first_request = after_first_request
        self.calls: list[dict] = []

    def request(self, params, **_):
        self.calls.append(dict(params))

        rows = sorted(
            (
                r
                for r in self.records
                if r["updated_at"] >= params.get("updated_after", "")
            ),
            key=lambda r: r["updated_at"],
        )
        start = (params["page"] - 1) * params["limit"]
        data = [dict(r) for r in rows[start : start + params["limit"]]]

        if len(self.calls) == 1 and self.after_first_request is not None:
            self.after_first_request(self.records)

        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "total_pages": -(-len(rows) // params["limit"]),
                "data": data,
            },
        )


def _cursor_resource(monkeypatch, api: _FakeApi) -> OvergradResource:
    monkeypatch.setattr(overgrad_resources.time, "sleep", lambda _: None)

    resource = OvergradResource(api_key="test", page_limit=2)
    object.__setattr__(resource, "_log", MagicMock())
    object.__setattr__(resource, "_session", api)

    return resource


def test_list_by_cursor_returns_every_record(monkeypatch):
    api = _FakeApi([{"id": i, "updated_at": _ts(i)} for i in range(1, 6)])

    data = _cursor_resource(monkeypatch, api).list_by_cursor(path="followings")

    assert {r["id"] for r in data} == {1, 2, 3, 4, 5}
    assert "updated_after" not in api.calls[0]
    assert api.calls[1]["updated_after"] == _ts(2)


def test_list_by_cursor_edit_mid_pull_skips_nothing(monkeypatch):
    # page-number paging skips id 3 here: id 1 moves to the end, id 3 slides
    # onto page 1, which was already read
    def edit(records):
        records[0]["updated_at"] = _ts(9)

    api = _FakeApi([{"id": i, "updated_at": _ts(i)} for i in range(1, 7)], edit)

    data = _cursor_resource(monkeypatch, api).list_by_cursor(path="followings")

    assert {r["id"] for r in data} == {1, 2, 3, 4, 5, 6}
    assert {"id": 1, "updated_at": _ts(9)} in data


def test_list_by_cursor_delete_mid_pull_skips_nothing(monkeypatch):
    def delete(records):
        del records[0]

    api = _FakeApi([{"id": i, "updated_at": _ts(i)} for i in range(1, 7)], delete)

    data = _cursor_resource(monkeypatch, api).list_by_cursor(path="followings")

    assert {r["id"] for r in data} >= {2, 3, 4, 5, 6}


def test_list_by_cursor_full_page_of_one_timestamp(monkeypatch):
    records = [{"id": i, "updated_at": _ts(1)} for i in range(1, 4)]
    api = _FakeApi([*records, {"id": 4, "updated_at": _ts(2)}])

    data = _cursor_resource(monkeypatch, api).list_by_cursor(path="followings")

    assert {r["id"] for r in data} == {1, 2, 3, 4}
    assert len(api.calls) < 10


def test_list_by_cursor_empty(monkeypatch):
    api = _FakeApi([])

    assert _cursor_resource(monkeypatch, api).list_by_cursor(path="followings") == []
    assert len(api.calls) == 1


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
