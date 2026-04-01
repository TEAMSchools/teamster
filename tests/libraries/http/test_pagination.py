from typing import Any
from unittest.mock import MagicMock

from requests import Response

from teamster.libraries.http.pagination import (
    paginate_cursor,
    paginate_offset,
    paginate_page,
)


def _mock_response(json_data: dict) -> Response:
    resp = MagicMock(spec=Response)
    resp.json.return_value = json_data
    resp.status_code = 200
    return resp


class TestPaginateCursor:
    def test_multi_page(self):
        responses = [
            _mock_response({"data": [{"id": 1}], "cursor": "abc"}),
            _mock_response({"data": [{"id": 2}], "cursor": None}),
        ]
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        pages = list(
            paginate_cursor(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["data"],
                extract_cursor=lambda r: r.json()["cursor"],
            )
        )

        assert pages == [[{"id": 1}], [{"id": 2}]]

    def test_empty_first_page(self):
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            call_count += 1
            return _mock_response({"data": [], "cursor": None})

        pages = list(
            paginate_cursor(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["data"],
                extract_cursor=lambda r: r.json()["cursor"],
            )
        )

        assert pages == [[]]

    def test_passes_page_params(self):
        captured_params: list[dict[str, Any]] = []
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            captured_params.append(dict(params))
            call_count += 1
            return _mock_response({"data": [{"id": 1}], "cursor": None})

        list(
            paginate_cursor(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["data"],
                extract_cursor=lambda r: r.json()["cursor"],
                page_params={"filter": "active"},
            )
        )

        assert "filter" in captured_params[0]
        assert captured_params[0]["filter"] == "active"


class TestPaginateOffset:
    def test_multi_page(self):
        page1_items = [{"id": i} for i in range(10)]
        page2_items = [{"id": i} for i in range(10, 15)]
        responses = [
            _mock_response({"items": page1_items}),
            _mock_response({"items": page2_items}),
        ]
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        pages = list(
            paginate_offset(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["items"],
                page_size=10,
            )
        )

        assert pages == [page1_items, page2_items]

    def test_empty_first_page(self):
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            call_count += 1
            return _mock_response({"items": []})

        pages = list(
            paginate_offset(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["items"],
                page_size=10,
            )
        )

        assert pages == [[]]

    def test_custom_param_names(self):
        captured_params: list[dict[str, Any]] = []
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            captured_params.append(dict(params))
            call_count += 1
            return _mock_response({"items": []})

        list(
            paginate_offset(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["items"],
                page_size=25,
                offset_param="$skip",
                limit_param="$top",
            )
        )

        assert "$skip" in captured_params[0]
        assert "$top" in captured_params[0]
        assert captured_params[0]["$top"] == 25

    def test_custom_stop_condition(self):
        page1_resp = MagicMock(spec=Response)
        page1_resp.json.return_value = {"items": [{"id": 1}]}
        page1_resp.status_code = 200

        page2_resp = MagicMock(spec=Response)
        page2_resp.json.return_value = {"items": []}
        page2_resp.status_code = 204

        responses = [page1_resp, page2_resp]
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        pages = list(
            paginate_offset(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["items"],
                page_size=10,
                is_last_page=lambda r: r.status_code == 204,
            )
        )

        assert pages == [[{"id": 1}], []]


class TestPaginatePage:
    def test_multi_page(self):
        page1_items = [{"id": i} for i in range(5)]
        page2_items = [{"id": 5}]
        responses = [
            _mock_response({"results": page1_items}),
            _mock_response({"results": page2_items}),
        ]
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        pages = list(
            paginate_page(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["results"],
                page_size=5,
            )
        )

        assert pages == [page1_items, page2_items]

    def test_empty_first_page(self):
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            call_count += 1
            return _mock_response({"results": []})

        pages = list(
            paginate_page(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["results"],
                page_size=10,
            )
        )

        assert pages == [[]]

    def test_custom_param_names(self):
        captured_params: list[dict[str, Any]] = []
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            captured_params.append(dict(params))
            call_count += 1
            return _mock_response({"results": []})

        list(
            paginate_page(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["results"],
                page_size=20,
                page_param="p",
                size_param="per_page",
            )
        )

        assert "p" in captured_params[0]
        assert "per_page" in captured_params[0]
        assert captured_params[0]["per_page"] == 20

    def test_start_page(self):
        captured_params: list[dict[str, Any]] = []
        call_count = 0

        def fetch_page(params):
            nonlocal call_count
            captured_params.append(dict(params))
            call_count += 1
            return _mock_response({"results": []})

        list(
            paginate_page(
                fetch_page=fetch_page,
                extract_records=lambda r: r.json()["results"],
                page_size=10,
                start=0,
            )
        )

        assert captured_params[0]["page"] == 0
