from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from requests import Session

from teamster.libraries.http.resources import BaseHTTPResource


def _make_resource(**kwargs) -> BaseHTTPResource:
    """Create a BaseHTTPResource with a mocked execution context.

    Args:
        **kwargs: Keyword arguments forwarded to BaseHTTPResource constructor.

    Returns:
        A BaseHTTPResource instance with setup_for_execution already called.
    """
    resource = BaseHTTPResource(**kwargs)
    ctx = MagicMock()
    ctx.log = MagicMock()
    resource.setup_for_execution(ctx)
    return resource


class TestLifecycle:
    def test_setup_assigns_log(self):
        resource = _make_resource()
        assert resource._log is not None

    def test_setup_calls_setup_session(self):
        resource = BaseHTTPResource()
        ctx = MagicMock()
        ctx.log = MagicMock()
        with patch.object(BaseHTTPResource, "_setup_session") as mock_setup:
            resource.setup_for_execution(ctx)
            mock_setup.assert_called_once()

    def test_teardown_closes_session(self):
        resource = _make_resource()
        ctx = MagicMock()
        with patch.object(resource._session, "close") as mock_close:
            resource.teardown_after_execution(ctx)
            mock_close.assert_called_once()

    def test_session_is_requests_session(self):
        resource = _make_resource()
        assert isinstance(resource._session, Session)


class TestRequestPipeline:
    def test_request_returns_response(self):
        resource = _make_resource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = timedelta(seconds=0.5)
        resource._session.request = MagicMock(return_value=mock_response)
        response = resource._request("GET", "https://example.com/api")
        assert response.status_code == 200

    def test_request_calls_prepare_request(self):
        resource = _make_resource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = timedelta(seconds=0.1)
        resource._session.request = MagicMock(return_value=mock_response)
        with patch.object(
            BaseHTTPResource, "_prepare_request", wraps=resource._prepare_request
        ) as mock_prepare:
            resource._request("GET", "https://example.com/api")
            mock_prepare.assert_called_once()

    def test_request_applies_timeout(self):
        resource = _make_resource(request_timeout=30.0)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = timedelta(seconds=0.1)
        resource._session.request = MagicMock(return_value=mock_response)
        resource._request("GET", "https://example.com/api")
        _, call_kwargs = resource._session.request.call_args
        assert call_kwargs.get("timeout") == 30.0

    def test_request_logs_info(self):
        resource = _make_resource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed = timedelta(seconds=0.25)
        resource._session.request = MagicMock(return_value=mock_response)
        resource._request("GET", "https://example.com/api")
        resource._log.info.assert_called_once()


class TestUrlConstruction:
    def test_get_url_joins_parts(self):
        resource = _make_resource()
        resource._base_url = "https://example.com/base"
        assert resource._get_url("v1", "users") == "https://example.com/base/v1/users"

    def test_get_url_single_part(self):
        resource = _make_resource()
        resource._base_url = "https://example.com/base"
        assert resource._get_url("users") == "https://example.com/base/users"

    def test_get_url_no_parts(self):
        resource = _make_resource()
        resource._base_url = "https://example.com/base"
        assert resource._get_url() == "https://example.com/base"


class TestConvenienceMethods:
    def test_get_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://example.com/base"
        with patch.object(BaseHTTPResource, "_request") as mock_request:
            resource.get("users", params={"page": 1})
            mock_request.assert_called_once_with(
                "GET", "https://example.com/base/users", params={"page": 1}
            )

    def test_post_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://example.com/base"
        with patch.object(BaseHTTPResource, "_request") as mock_request:
            resource.post("users", json={"name": "test"})
            mock_request.assert_called_once_with(
                "POST", "https://example.com/base/users", json={"name": "test"}
            )

    def test_put_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://example.com/base"
        with patch.object(BaseHTTPResource, "_request") as mock_request:
            resource.put("users", "123", json={"name": "updated"})
            mock_request.assert_called_once_with(
                "PUT",
                "https://example.com/base/users/123",
                json={"name": "updated"},
            )

    def test_delete_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://example.com/base"
        with patch.object(BaseHTTPResource, "_request") as mock_request:
            resource.delete("users", "123")
            mock_request.assert_called_once_with(
                "DELETE", "https://example.com/base/users/123"
            )
