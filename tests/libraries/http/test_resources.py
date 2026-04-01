import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from requests import Session
from requests.exceptions import HTTPError
from requests.models import Response as RealResponse

from teamster.libraries.adp.workforce_now.api.resources import (
    AdpWorkforceNowResource,
)
from teamster.libraries.coupa.resources import CoupaResource
from teamster.libraries.deanslist.resources import DeansListResource
from teamster.libraries.http.resources import BaseHTTPResource
from teamster.libraries.knowbe4.resources import KnowBe4Resource
from teamster.libraries.level_data.grow.resources import GrowResource
from teamster.libraries.overgrad.resources import OvergradResource
from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)
from teamster.libraries.smartrecruiters.resources import SmartRecruitersResource
from teamster.libraries.zendesk.resources import ZendeskResource


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
        # trunk-ignore(pyright/reportAttributeAccessIssue): _log is a MagicMock
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


def _make_error_response(status_code: int, text: str = "error") -> RealResponse:
    response = RealResponse()
    response.status_code = status_code
    response._content = text.encode()
    return response


class TestErrorHandling:
    def test_429_reads_retry_after_header(self):
        resource = _make_resource()
        r429 = _make_error_response(429)
        r429.headers["Retry-After"] = "2"
        r200 = _make_error_response(200)
        resource._session.request = MagicMock(side_effect=[r429, r200])
        with patch("teamster.libraries.http.resources.time.sleep") as mock_sleep:
            result = resource._request("GET", "https://example.com/api")
        assert result.status_code == 200
        mock_sleep.assert_any_call(2.0)

    def test_429_without_retry_after_uses_backoff(self):
        resource = _make_resource()
        r429 = _make_error_response(429)
        r200 = _make_error_response(200)
        resource._session.request = MagicMock(side_effect=[r429, r200])
        with patch("teamster.libraries.http.resources.time.sleep"):
            result = resource._request("GET", "https://example.com/api")
        assert result.status_code == 200

    def test_5xx_retries_with_backoff(self):
        resource = _make_resource()
        r500 = _make_error_response(500)
        r200 = _make_error_response(200)
        resource._session.request = MagicMock(side_effect=[r500, r200])
        with patch("teamster.libraries.http.resources.time.sleep"):
            result = resource._request("GET", "https://example.com/api")
        assert result.status_code == 200

    def test_401_calls_reauthenticate_once(self):
        resource = _make_resource()
        r401a = _make_error_response(401)
        r401b = _make_error_response(401)
        resource._session.request = MagicMock(side_effect=[r401a, r401b])
        with (
            patch.object(BaseHTTPResource, "_reauthenticate") as mock_reauth,
            pytest.raises(HTTPError),
        ):
            resource._request("GET", "https://example.com/api")
        mock_reauth.assert_called_once()

    def test_401_then_success(self):
        resource = _make_resource()
        r401 = _make_error_response(401)
        r200 = _make_error_response(200)
        resource._session.request = MagicMock(side_effect=[r401, r200])
        with patch.object(BaseHTTPResource, "_reauthenticate"):
            result = resource._request("GET", "https://example.com/api")
        assert result.status_code == 200

    def test_4xx_non_retryable_raises_immediately(self):
        resource = _make_resource()
        r403 = _make_error_response(403)
        resource._session.request = MagicMock(return_value=r403)
        with pytest.raises(HTTPError):
            resource._request("GET", "https://example.com/api")

    def test_max_retries_exhausted(self):
        resource = _make_resource()
        r500 = _make_error_response(500)
        resource._session.request = MagicMock(side_effect=[r500, r500, r500])
        with (
            patch("teamster.libraries.http.resources.time.sleep"),
            pytest.raises(HTTPError),
        ):
            resource._request("GET", "https://example.com/api")

    def test_get_retry_after_parses_seconds(self):
        resource = _make_resource()
        response = RealResponse()
        response.headers["Retry-After"] = "30"
        result = resource._get_retry_after(response)
        assert result == 30.0

    def test_get_retry_after_parses_http_date(self):
        resource = _make_resource()
        response = RealResponse()
        now_dt = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
        response.headers["Retry-After"] = "Tue, 01 Apr 2026 12:00:05 GMT"
        with patch("teamster.libraries.http.resources.datetime") as mock_dt:
            mock_dt.now.return_value = now_dt
            result = resource._get_retry_after(response)
        assert result == pytest.approx(5.0)

    def test_get_retry_after_parses_x_ratelimit_reset(self):
        resource = _make_resource()
        response = RealResponse()
        reset_epoch = 1000010.0
        response.headers["X-RateLimit-Reset"] = str(reset_epoch)
        with patch(
            "teamster.libraries.http.resources.time.time", return_value=1000000.0
        ):
            result = resource._get_retry_after(response)
        assert result is not None
        assert abs(result - 10.0) < 0.1

    def test_get_retry_after_returns_none_when_no_headers(self):
        resource = _make_resource()
        response = RealResponse()
        result = resource._get_retry_after(response)
        assert result is None


class TestSmartRecruitersResource:
    def _make(self) -> SmartRecruitersResource:
        resource = SmartRecruitersResource(smart_token="test-token")
        ctx = MagicMock()
        ctx.log = MagicMock()
        resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_smart_token_header(self):
        resource = self._make()
        assert resource._session.headers["X-SmartToken"] == "test-token"

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("reporting", "reports")
            == "https://api.smartrecruiters.com/reporting/reports"
        )

    def test_inherits_retry(self):
        resource = self._make()
        resp_500 = _make_error_response(500)
        resp_200 = MagicMock(status_code=200)
        resp_200.raise_for_status = MagicMock()
        resp_200.elapsed.total_seconds.return_value = 0.1
        with patch.object(
            resource._session, "request", side_effect=[resp_500, resp_200]
        ):
            with patch("teamster.libraries.http.resources.time.sleep"):
                result = resource._request("GET", "https://example.com")
                assert result.status_code == 200


class TestPowerSchoolEnrollmentResource:
    def _make(self) -> PowerSchoolEnrollmentResource:
        resource = PowerSchoolEnrollmentResource(api_key="test-key")
        ctx = MagicMock()
        ctx.log = MagicMock()
        resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_basic_auth(self):
        resource = self._make()
        assert resource._session.auth == ("test-key", "")

    def test_get_url_with_version(self):
        resource = self._make()
        assert (
            resource._get_url("schools")
            == "https://registration.powerschool.com/api/v1/schools"
        )

    def test_get_url_with_extra_parts(self):
        resource = self._make()
        assert (
            resource._get_url("schools", "123")
            == "https://registration.powerschool.com/api/v1/schools/123"
        )


class TestOvergradResource:
    def _make(self) -> OvergradResource:
        resource = OvergradResource(api_key="test-key")
        ctx = MagicMock()
        ctx.log = MagicMock()
        resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_api_key_header(self):
        resource = self._make()
        assert resource._session.headers["ApiKey"] == "test-key"

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("students") == "https://api.overgrad.com/api/v1/students"
        )

    def test_get_url_with_extra_parts(self):
        resource = self._make()
        assert (
            resource._get_url("students", "123")
            == "https://api.overgrad.com/api/v1/students/123"
        )


class TestKnowBe4Resource:
    def _make(self) -> KnowBe4Resource:
        resource = KnowBe4Resource(api_key="test-key", server="us")
        ctx = MagicMock()
        ctx.log = MagicMock()
        resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_bearer_header(self):
        resource = self._make()
        assert resource._session.headers["Authorization"] == "Bearer test-key"

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("training", "enrollments")
            == "https://us.api.knowbe4.com/v1/training/enrollments"
        )

    def test_base_url_includes_server(self):
        resource = self._make()
        assert resource._base_url == "https://us.api.knowbe4.com"


class TestZendeskResource:
    def _make(self) -> ZendeskResource:
        resource = ZendeskResource(
            subdomain="test", email="user@example.com", token="test-token"
        )
        ctx = MagicMock()
        ctx.log = MagicMock()
        resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_basic_auth(self):
        resource = self._make()
        assert resource._session.auth is not None

    def test_setup_sets_content_type(self):
        resource = self._make()
        assert resource._session.headers["Content-Type"] == "application/json"

    def test_get_url(self):
        resource = self._make()
        assert resource._get_url("tickets") == "https://test.zendesk.com/api/v2/tickets"

    def test_get_retry_after_parses_ratelimit_remaining(self):
        resource = self._make()
        resp = _make_error_response(429)
        resp.headers["ratelimit-remaining"] = "0"
        resp.headers["ratelimit-reset"] = str(time.time() + 5)
        result = resource._get_retry_after(resp)
        assert result is not None
        assert result > 0


class TestCoupaResource:
    def _make(self) -> CoupaResource:
        resource = CoupaResource(
            instance_url="test.coupahost.com",
            client_id="cid",
            client_secret="csec",
            scope=["core.read"],
        )
        ctx = MagicMock()
        ctx.log = MagicMock()
        with patch("teamster.libraries.coupa.resources.OAuth2Session") as mock_oauth:
            mock_session = MagicMock()
            mock_session.fetch_token.return_value = {"access_token": "test-token"}
            mock_session.headers = {}
            mock_oauth.return_value = mock_session
            resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_bearer_header(self):
        resource = self._make()
        assert "Bearer" in str(resource._session.headers.get("Authorization", ""))

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("purchase_orders")
            == "https://test.coupahost.com/api/purchase_orders"
        )


class TestGrowResource:
    def _make(self) -> GrowResource:
        resource = GrowResource(
            client_id="cid",
            client_secret="csec",
            district_id="dist-1",
        )
        ctx = MagicMock()
        ctx.log = MagicMock()
        with patch(
            "teamster.libraries.level_data.grow.resources.OAuth2Session"
        ) as mock_oauth:
            mock_oauth_instance = MagicMock()
            mock_oauth_instance.fetch_token.return_value = {
                "access_token": "test-token"
            }
            mock_oauth.return_value = mock_oauth_instance
            resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_bearer_header(self):
        resource = self._make()
        # trunk-ignore(pyright/reportOperatorIssue): headers values are str at runtime
        assert "Bearer test-token" in resource._session.headers.get("Authorization", "")

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("schools")
            == "https://grow-api.leveldata.com/external/schools"
        )

    def test_get_url_with_id(self):
        resource = self._make()
        assert (
            resource._get_url("schools", "123")
            == "https://grow-api.leveldata.com/external/schools/123"
        )


class TestAdpWorkforceNowResource:
    def _make(self) -> AdpWorkforceNowResource:
        resource = AdpWorkforceNowResource(
            client_id="cid",
            client_secret="csec",
            cert_filepath="/tmp/cert.pem",
            key_filepath="/tmp/key.pem",
        )
        ctx = MagicMock()
        ctx.log = MagicMock()
        with patch(
            "teamster.libraries.adp.workforce_now.api.resources.OAuth2Session"
        ) as mock_oauth:
            mock_session = MagicMock()
            mock_session.fetch_token.return_value = {"access_token": "test-token"}
            mock_session.headers = {}
            mock_oauth.return_value = mock_session
            resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_bearer_header(self):
        resource = self._make()
        assert "Bearer" in str(resource._session.headers.get("Authorization", ""))

    def test_setup_sets_cert(self):
        resource = self._make()
        assert resource._session.cert == ("/tmp/cert.pem", "/tmp/key.pem")

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("hr", "v2", "workers")
            == "https://api.adp.com/hr/v2/workers"
        )

    def test_post_action_url_pattern(self):
        resource = self._make()
        with patch.object(AdpWorkforceNowResource, "_request") as mock:
            mock.return_value = MagicMock(status_code=200)
            resource.post_action("hr/v2/workers", "request", "submit", payload={})
            mock.assert_called_once_with(
                "POST",
                "https://api.adp.com/hr/v2/workers.request.submit",
                json={},
            )


class TestDeansListResource:
    def _make(self) -> DeansListResource:
        resource = DeansListResource(
            subdomain="test-district",
            api_key_map="/tmp/fake-key-map.yaml",
        )
        ctx = MagicMock()
        ctx.log = MagicMock()
        with patch("builtins.open", create=True) as mock_open:
            from io import StringIO

            mock_open.return_value.__enter__ = MagicMock(
                return_value=StringIO("api_key_map:\n  100: key-100\n  200: key-200")
            )
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            resource.setup_for_execution(ctx)
        return resource

    def test_base_url(self):
        resource = self._make()
        assert resource._base_url == "https://test-district.deanslistsoftware.com/api"

    def test_get_url_versioned(self):
        resource = self._make()
        assert (
            resource._get_url("v1", "students")
            == "https://test-district.deanslistsoftware.com/api/v1/students"
        )

    def test_get_url_beta(self):
        resource = self._make()
        url = resource._get_url("beta", "behavior")
        assert url.endswith("/beta/export/get-behavior-data.php")

    def test_get_url_beta_no_data_suffix(self):
        resource = self._make()
        url = resource._get_url("beta", "suspensions")
        assert url.endswith("/beta/export/get-suspensions.php")

    def test_prepare_request_injects_apikey(self):
        resource = self._make()
        resource._current_school_id = 100
        _, _, kwargs = resource._prepare_request(
            "GET",
            "https://example.com",
            {"params": {"page": 1}},
        )
        assert kwargs["params"]["apikey"] == "key-100"
