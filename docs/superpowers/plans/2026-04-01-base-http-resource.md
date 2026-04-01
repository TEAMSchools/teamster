# Base HTTP Resource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract a reusable `BaseHTTPResource` base class from 9 existing
Dagster HTTP resource classes, eliminating duplicated session lifecycle, retry,
error handling, and pagination logic.

**Architecture:** Hook-based single-inheritance base class. Each subclass
overrides only what it needs — auth setup (`_setup_session`), URL format
(`_get_url`), error handling (`_handle_error`), or request preparation
(`_prepare_request`). The base provides built-in retry via tenacity,
standardized error handling with rate-limit awareness, and pagination helpers
for cursor, offset, and page patterns.

**Tech Stack:** Python 3.13, Dagster `ConfigurableResource`, `requests`,
`tenacity`, `unittest.mock` (for tests)

**Spec:** `docs/superpowers/specs/2026-03-25-base-http-resource-design.md`

---

## File Structure

| File                                        | Responsibility                                   |
| ------------------------------------------- | ------------------------------------------------ |
| `src/teamster/libraries/http/__init__.py`   | Package init                                     |
| `src/teamster/libraries/http/resources.py`  | `BaseHTTPResource` base class                    |
| `src/teamster/libraries/http/pagination.py` | Three pagination helpers as standalone functions |
| `tests/libraries/http/__init__.py`          | Test package init                                |
| `tests/libraries/http/test_resources.py`    | Base class unit tests                            |
| `tests/libraries/http/test_pagination.py`   | Pagination helper unit tests                     |

Migrated subclasses remain in their existing files — no file moves.

## Code Location Validation Matrix

After each tier, the implementer must ask someone with env vars to run
`dagster definitions validate` for affected code locations. Claude sessions
cannot run this (env vars are blocked by hooks).

| Resource                      | Code Locations                    |
| ----------------------------- | --------------------------------- |
| SmartRecruitersResource       | kipptaf                           |
| PowerSchoolEnrollmentResource | kipptaf                           |
| OvergradResource              | kipptaf, kippnewark, kippcamden   |
| KnowBe4Resource               | kipptaf                           |
| ZendeskResource               | kipptaf                           |
| CoupaResource                 | kipptaf                           |
| GrowResource                  | kipptaf                           |
| AdpWorkforceNowResource       | kipptaf                           |
| DeansListResource             | kippnewark, kippcamden, kippmiami |

Note: Overgrad and DeansList have singleton instances in
`src/teamster/core/resources.py`.

---

## Task 1: Base class — session lifecycle and `_request` pipeline

**Files:**

- Create: `src/teamster/libraries/http/__init__.py`
- Create: `src/teamster/libraries/http/resources.py`
- Create: `tests/libraries/http/__init__.py`
- Create: `tests/libraries/http/test_resources.py`

### Step 1.1: Write lifecycle tests

- [ ] **Create test file with lifecycle tests**

```python
# tests/libraries/http/__init__.py
```

```python
# tests/libraries/http/test_resources.py
from unittest.mock import MagicMock, patch

import pytest
from requests import Session

from teamster.libraries.http.resources import BaseHTTPResource


def _make_resource(**kwargs) -> BaseHTTPResource:
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
        with patch.object(BaseHTTPResource, "_setup_session") as mock:
            _make_resource()
            mock.assert_called_once()

    def test_teardown_closes_session(self):
        resource = _make_resource()
        with patch.object(resource._session, "close") as mock:
            ctx = MagicMock()
            resource.teardown_after_execution(ctx)
            mock.assert_called_once()

    def test_session_is_requests_session(self):
        resource = _make_resource()
        assert isinstance(resource._session, Session)
```

- [ ] **Run tests to verify they fail**

Run: `uv run pytest tests/libraries/http/test_resources.py::TestLifecycle -v`
Expected: FAIL —
`ModuleNotFoundError: No module named 'teamster.libraries.http'`

### Step 1.2: Implement lifecycle

- [ ] **Create the base class with lifecycle methods**

```python
# src/teamster/libraries/http/__init__.py
```

```python
# src/teamster/libraries/http/resources.py
from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import HTTPError


class BaseHTTPResource(ConfigurableResource):
    request_timeout: float = 60.0

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr(default="")
    _log: DagsterLogManager = PrivateAttr()

    def setup_for_execution(self, context: InitResourceContext) -> None:
        self._log = check.not_none(value=context.log)
        self._setup_session()

    def teardown_after_execution(self, context: InitResourceContext) -> None:
        self._session.close()

    def _setup_session(self) -> None:
        """Override in subclasses to configure auth, headers, base URL."""
```

- [ ] **Run tests to verify they pass**

Run: `uv run pytest tests/libraries/http/test_resources.py::TestLifecycle -v`
Expected: 4 passed

### Step 1.3: Write request pipeline tests

- [ ] **Add request pipeline tests**

Append to `tests/libraries/http/test_resources.py`:

```python
class TestRequestPipeline:
    def test_request_returns_response(self):
        resource = _make_resource()
        with patch.object(resource._session, "request") as mock:
            mock.return_value = MagicMock(status_code=200)
            mock.return_value.raise_for_status = MagicMock()
            response = resource._request("GET", "https://example.com")
            assert response.status_code == 200

    def test_request_calls_prepare_request(self):
        resource = _make_resource()
        with patch.object(resource._session, "request") as mock_req:
            mock_req.return_value = MagicMock(status_code=200)
            mock_req.return_value.raise_for_status = MagicMock()
            with patch.object(
                resource, "_prepare_request", wraps=resource._prepare_request
            ) as mock_prep:
                resource._request("GET", "https://example.com", params={"a": 1})
                mock_prep.assert_called_once()

    def test_request_applies_timeout(self):
        resource = _make_resource(request_timeout=30.0)
        with patch.object(resource._session, "request") as mock:
            mock.return_value = MagicMock(status_code=200)
            mock.return_value.raise_for_status = MagicMock()
            resource._request("GET", "https://example.com")
            _, kwargs = mock.call_args
            assert kwargs["timeout"] == 30.0

    def test_request_logs_info(self):
        resource = _make_resource()
        with patch.object(resource._session, "request") as mock:
            mock_resp = MagicMock(status_code=200)
            mock_resp.raise_for_status = MagicMock()
            mock_resp.elapsed.total_seconds.return_value = 0.5
            mock.return_value = mock_resp
            resource._request("GET", "https://example.com")
            resource._log.info.assert_called_once()
```

- [ ] **Run tests to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestRequestPipeline -v`
Expected: FAIL —
`AttributeError: 'BaseHTTPResource' object has no attribute '_request'`

### Step 1.4: Implement request pipeline

- [ ] **Add `_prepare_request` and `_request` to `BaseHTTPResource`**

Add these methods to `BaseHTTPResource` in
`src/teamster/libraries/http/resources.py`:

```python
    def _prepare_request(
        self, method: str, url: str, kwargs: dict
    ) -> tuple[str, str, dict]:
        """Pre-request hook. Override to inject params, headers, etc."""
        return method, url, kwargs

    def _request(self, method: str, url: str, **kwargs) -> Response:
        kwargs.setdefault("timeout", self.request_timeout)
        method, url, kwargs = self._prepare_request(method, url, kwargs)

        response = self._session.request(method=method, url=url, **kwargs)
        self._log.info(
            f"{method} {url} -> {response.status_code}"
            f" ({response.elapsed.total_seconds():.2f}s)"
        )

        response.raise_for_status()
        return response
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestRequestPipeline -v`
Expected: 4 passed

### Step 1.5: Write URL construction and convenience method tests

- [ ] **Add URL and convenience method tests**

Append to `tests/libraries/http/test_resources.py`:

```python
class TestUrlConstruction:
    def test_get_url_joins_parts(self):
        resource = _make_resource()
        resource._base_url = "https://api.example.com"
        assert resource._get_url("v1", "users") == "https://api.example.com/v1/users"

    def test_get_url_single_part(self):
        resource = _make_resource()
        resource._base_url = "https://api.example.com"
        assert resource._get_url("users") == "https://api.example.com/users"

    def test_get_url_no_parts(self):
        resource = _make_resource()
        resource._base_url = "https://api.example.com"
        assert resource._get_url() == "https://api.example.com"


class TestConvenienceMethods:
    def test_get_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://api.example.com"
        with patch.object(resource, "_request") as mock:
            mock.return_value = MagicMock(status_code=200)
            resource.get("users", params={"page": 1})
            mock.assert_called_once_with(
                "GET", "https://api.example.com/users", params={"page": 1}
            )

    def test_post_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://api.example.com"
        with patch.object(resource, "_request") as mock:
            mock.return_value = MagicMock(status_code=201)
            resource.post("users", json={"name": "test"})
            mock.assert_called_once_with(
                "POST", "https://api.example.com/users", json={"name": "test"}
            )

    def test_put_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://api.example.com"
        with patch.object(resource, "_request") as mock:
            mock.return_value = MagicMock(status_code=200)
            resource.put("users", "123", json={"name": "updated"})
            mock.assert_called_once_with(
                "PUT", "https://api.example.com/users/123", json={"name": "updated"}
            )

    def test_delete_delegates_to_request(self):
        resource = _make_resource()
        resource._base_url = "https://api.example.com"
        with patch.object(resource, "_request") as mock:
            mock.return_value = MagicMock(status_code=204)
            resource.delete("users", "123")
            mock.assert_called_once_with(
                "DELETE", "https://api.example.com/users/123"
            )
```

- [ ] **Run tests to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestUrlConstruction -v`
Expected: FAIL —
`AttributeError: 'BaseHTTPResource' object has no attribute '_get_url'`

### Step 1.6: Implement URL construction and convenience methods

- [ ] **Add `_get_url` and verb methods to `BaseHTTPResource`**

Add these methods to `BaseHTTPResource` in
`src/teamster/libraries/http/resources.py`:

```python
    def _get_url(self, *parts: str) -> str:
        """Joins _base_url with path segments. Override for custom URL formats."""
        if parts:
            return self._base_url + "/" + "/".join(parts)
        return self._base_url

    def get(self, *parts: str, **kwargs) -> Response:
        return self._request("GET", self._get_url(*parts), **kwargs)

    def post(self, *parts: str, **kwargs) -> Response:
        return self._request("POST", self._get_url(*parts), **kwargs)

    def put(self, *parts: str, **kwargs) -> Response:
        return self._request("PUT", self._get_url(*parts), **kwargs)

    def delete(self, *parts: str, **kwargs) -> Response:
        return self._request("DELETE", self._get_url(*parts), **kwargs)
```

- [ ] **Run all tests to verify they pass**

Run: `uv run pytest tests/libraries/http/test_resources.py -v` Expected: 12
passed

### Step 1.7: Commit

- [ ] **Commit base class skeleton**

```bash
git add src/teamster/libraries/http/__init__.py src/teamster/libraries/http/resources.py tests/libraries/http/__init__.py tests/libraries/http/test_resources.py
git commit -m "feat(http): add BaseHTTPResource with lifecycle, request pipeline, and URL construction"
```

---

## Task 2: Error handling and retry

**Files:**

- Modify: `src/teamster/libraries/http/resources.py`
- Modify: `tests/libraries/http/test_resources.py`

### Step 2.1: Write error handling tests

- [ ] **Add error handling and retry tests**

Append to `tests/libraries/http/test_resources.py`:

```python
from unittest.mock import MagicMock, call, patch

from requests.exceptions import HTTPError
from requests.models import Response as RealResponse


def _make_error_response(status_code: int, text: str = "error") -> RealResponse:
    response = RealResponse()
    response.status_code = status_code
    response._content = text.encode()
    return response


class TestErrorHandling:
    def test_429_reads_retry_after_header(self):
        resource = _make_resource()
        resp_429 = _make_error_response(429)
        resp_429.headers["Retry-After"] = "2"
        resp_200 = MagicMock(status_code=200)
        resp_200.raise_for_status = MagicMock()
        resp_200.elapsed.total_seconds.return_value = 0.1
        with patch.object(
            resource._session, "request", side_effect=[resp_429, resp_200]
        ):
            with patch("teamster.libraries.http.resources.time.sleep") as mock_sleep:
                result = resource._request("GET", "https://example.com")
                assert result.status_code == 200
                mock_sleep.assert_called_with(2.0)

    def test_429_without_retry_after_uses_backoff(self):
        resource = _make_resource()
        resp_429 = _make_error_response(429)
        resp_200 = MagicMock(status_code=200)
        resp_200.raise_for_status = MagicMock()
        resp_200.elapsed.total_seconds.return_value = 0.1
        with patch.object(
            resource._session, "request", side_effect=[resp_429, resp_200]
        ):
            with patch("teamster.libraries.http.resources.time.sleep"):
                result = resource._request("GET", "https://example.com")
                assert result.status_code == 200

    def test_5xx_retries_with_backoff(self):
        resource = _make_resource()
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

    def test_401_calls_reauthenticate_once(self):
        resource = _make_resource()
        resp_401_1 = _make_error_response(401)
        resp_401_2 = _make_error_response(401)
        with patch.object(
            resource._session, "request", side_effect=[resp_401_1, resp_401_2]
        ):
            with patch.object(resource, "_reauthenticate") as mock_reauth:
                with patch("teamster.libraries.http.resources.time.sleep"):
                    with pytest.raises(HTTPError):
                        resource._request("GET", "https://example.com")
                    mock_reauth.assert_called_once()

    def test_401_then_success(self):
        resource = _make_resource()
        resp_401 = _make_error_response(401)
        resp_200 = MagicMock(status_code=200)
        resp_200.raise_for_status = MagicMock()
        resp_200.elapsed.total_seconds.return_value = 0.1
        with patch.object(
            resource._session, "request", side_effect=[resp_401, resp_200]
        ):
            with patch.object(resource, "_reauthenticate"):
                with patch("teamster.libraries.http.resources.time.sleep"):
                    result = resource._request("GET", "https://example.com")
                    assert result.status_code == 200

    def test_4xx_non_retryable_raises_immediately(self):
        resource = _make_resource()
        resp_403 = _make_error_response(403)
        with patch.object(resource._session, "request", return_value=resp_403):
            with pytest.raises(HTTPError):
                resource._request("GET", "https://example.com")

    def test_max_retries_exhausted(self):
        resource = _make_resource()
        responses = [_make_error_response(500) for _ in range(3)]
        with patch.object(resource._session, "request", side_effect=responses):
            with patch("teamster.libraries.http.resources.time.sleep"):
                with pytest.raises(HTTPError):
                    resource._request("GET", "https://example.com")

    def test_get_retry_after_parses_seconds(self):
        resource = _make_resource()
        resp = _make_error_response(429)
        resp.headers["Retry-After"] = "30"
        assert resource._get_retry_after(resp) == 30.0

    def test_get_retry_after_parses_http_date(self):
        resource = _make_resource()
        resp = _make_error_response(429)
        # Wed, 01 Apr 2026 12:00:05 GMT — 5 seconds from "now"
        resp.headers["Retry-After"] = "Wed, 01 Apr 2026 12:00:05 GMT"
        with patch(
            "teamster.libraries.http.resources.datetime"
        ) as mock_dt:
            from datetime import datetime, timezone

            mock_dt.now.return_value = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = resource._get_retry_after(resp)
            assert result == pytest.approx(5.0, abs=1.0)

    def test_get_retry_after_parses_x_ratelimit_reset(self):
        resource = _make_resource()
        resp = _make_error_response(429)
        # epoch timestamp 10 seconds from "now"
        resp.headers["X-RateLimit-Reset"] = "1743508810"
        with patch("teamster.libraries.http.resources.time.time", return_value=1743508800.0):
            result = resource._get_retry_after(resp)
            assert result == pytest.approx(10.0, abs=1.0)

    def test_get_retry_after_returns_none_when_no_headers(self):
        resource = _make_resource()
        resp = _make_error_response(429)
        assert resource._get_retry_after(resp) is None
```

- [ ] **Run tests to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestErrorHandling -v`
Expected: FAIL — multiple attribute errors

### Step 2.2: Implement error handling and retry

- [ ] **Add retry, error handling, and rate-limit parsing**

Update imports at top of `src/teamster/libraries/http/resources.py`:

```python
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import Response, Session
from requests.exceptions import HTTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
```

Replace the existing `_request` method and add new methods:

```python
    def _handle_error(self, response: Response, error: HTTPError) -> None:
        """Error hook called on HTTPError. Override for custom behavior."""
        status = response.status_code

        if status == 429:
            wait = self._get_retry_after(response)
            if wait is not None:
                time.sleep(wait)
            raise error

        if status == 401:
            if not self._reauth_attempted:
                self._reauth_attempted = True
                self._reauthenticate()
                raise error
            # Already tried re-auth — don't loop
            self._log.error(
                f"{response.request.method} {response.request.url}"
                f" -> {status} (re-auth failed)\n{response.text}"
            )
            raise error

        if 500 <= status < 600:
            self._log.error(
                f"{response.request.method} {response.request.url}"
                f" -> {status}\n{response.text}"
            )
            raise error

        # Non-retryable (4xx other than 401/429)
        self._log.error(
            f"{response.request.method} {response.request.url}"
            f" -> {status}\n{response.text}"
        )
        raise error

    def _get_retry_after(self, response: Response) -> float | None:
        """Parse rate-limit wait time. Override for non-standard formats."""
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                parsed = parsedate_to_datetime(retry_after)
                return (parsed - datetime.now(tz=timezone.utc)).total_seconds()

        reset = response.headers.get("X-RateLimit-Reset")
        if reset is not None:
            return float(reset) - time.time()

        return None

    def _reauthenticate(self) -> None:
        """Called on 401. Override with token refresh logic."""
        raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type(HTTPError),
        reraise=True,
    )
    def _request(self, method: str, url: str, **kwargs) -> Response:
        self._reauth_attempted = False
        kwargs.setdefault("timeout", self.request_timeout)
        method, url, kwargs = self._prepare_request(method, url, kwargs)

        response = self._session.request(method=method, url=url, **kwargs)
        self._log.info(
            f"{method} {url} -> {response.status_code}"
            f" ({response.elapsed.total_seconds():.2f}s)"
        )

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._handle_error(response, e)
            raise  # unreachable — _handle_error always raises, but satisfies type checker
```

Note: the `_reauth_attempted` flag is set at the top of `_request` (reset per
call) and checked in `_handle_error`. The tenacity `@retry` decorator wraps the
entire method, so retries re-enter at the top and reset the flag — but
`_handle_error` sets it to `True` before raising, so the second 401 within the
same retry cycle sees it as `True`.

Actually, the flag reset must happen **outside** the retry loop to work
correctly. Move it to a wrapper:

```python
    def _request(self, method: str, url: str, **kwargs) -> Response:
        self._reauth_attempted = False
        return self._request_with_retry(method, url, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type(HTTPError),
        reraise=True,
    )
    def _request_with_retry(self, method: str, url: str, **kwargs) -> Response:
        kwargs.setdefault("timeout", self.request_timeout)
        method, url, kwargs = self._prepare_request(method, url, kwargs)

        response = self._session.request(method=method, url=url, **kwargs)
        self._log.info(
            f"{method} {url} -> {response.status_code}"
            f" ({response.elapsed.total_seconds():.2f}s)"
        )

        try:
            response.raise_for_status()
            return response
        except HTTPError as e:
            self._handle_error(response, e)
            raise  # unreachable — satisfies type checker
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestErrorHandling -v`
Expected: 12 passed

- [ ] **Run full test file**

Run: `uv run pytest tests/libraries/http/test_resources.py -v` Expected: 24
passed

### Step 2.3: Commit

- [ ] **Commit error handling and retry**

```bash
git add src/teamster/libraries/http/resources.py tests/libraries/http/test_resources.py
git commit -m "feat(http): add retry, error handling, rate-limit parsing, and re-auth guard"
```

---

## Task 3: Pagination helpers

**Files:**

- Create: `src/teamster/libraries/http/pagination.py`
- Create: `tests/libraries/http/test_pagination.py`

### Step 3.1: Write pagination tests

- [ ] **Create pagination test file**

```python
# tests/libraries/http/test_pagination.py
from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
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
        pages = [
            _mock_response({"data": [{"id": 1}], "meta": {"cursor": "abc"}}),
            _mock_response({"data": [{"id": 2}], "meta": {"cursor": None}}),
        ]
        call_count = 0

        def fetch_page(params: dict) -> Response:
            nonlocal call_count
            resp = pages[call_count]
            call_count += 1
            return resp

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["data"]

        def extract_cursor(resp: Response) -> str | None:
            return resp.json()["meta"]["cursor"]

        result = list(paginate_cursor(fetch_page, extract_records, extract_cursor))
        assert result == [[{"id": 1}], [{"id": 2}]]

    def test_empty_first_page(self):
        pages = [_mock_response({"data": [], "meta": {"cursor": None}})]

        def fetch_page(params: dict) -> Response:
            return pages[0]

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["data"]

        def extract_cursor(resp: Response) -> str | None:
            return resp.json()["meta"]["cursor"]

        result = list(paginate_cursor(fetch_page, extract_records, extract_cursor))
        assert result == [[]]

    def test_passes_page_params(self):
        pages = [_mock_response({"data": [{"id": 1}], "meta": {"cursor": None}})]
        captured_params: list[dict] = []

        def fetch_page(params: dict) -> Response:
            captured_params.append(params.copy())
            return pages[0]

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["data"]

        def extract_cursor(resp: Response) -> str | None:
            return resp.json()["meta"]["cursor"]

        list(
            paginate_cursor(
                fetch_page,
                extract_records,
                extract_cursor,
                page_params={"filter": "active"},
            )
        )
        assert captured_params[0]["filter"] == "active"


class TestPaginateOffset:
    def test_multi_page(self):
        pages = [
            _mock_response({"items": [{"id": i} for i in range(10)]}),
            _mock_response({"items": [{"id": i} for i in range(10, 15)]}),
        ]
        call_count = 0

        def fetch_page(params: dict) -> Response:
            nonlocal call_count
            resp = pages[call_count]
            call_count += 1
            return resp

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["items"]

        result = list(paginate_offset(fetch_page, extract_records, page_size=10))
        assert result == [
            [{"id": i} for i in range(10)],
            [{"id": i} for i in range(10, 15)],
        ]

    def test_empty_first_page(self):
        pages = [_mock_response({"items": []})]

        def fetch_page(params: dict) -> Response:
            return pages[0]

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["items"]

        result = list(paginate_offset(fetch_page, extract_records, page_size=10))
        assert result == [[]]

    def test_custom_param_names(self):
        pages = [_mock_response({"items": []})]
        captured_params: list[dict] = []

        def fetch_page(params: dict) -> Response:
            captured_params.append(params.copy())
            return pages[0]

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["items"]

        list(
            paginate_offset(
                fetch_page,
                extract_records,
                page_size=100,
                offset_param="$skip",
                limit_param="$top",
            )
        )
        assert "$skip" in captured_params[0]
        assert "$top" in captured_params[0]

    def test_custom_stop_condition(self):
        """ADP WFN stops on HTTP 204 instead of short page."""
        pages = [
            _mock_response({"items": [{"id": 1}]}),
            MagicMock(spec=Response, status_code=204),
        ]
        pages[1].json.return_value = {"items": []}
        call_count = 0

        def fetch_page(params: dict) -> Response:
            nonlocal call_count
            resp = pages[call_count]
            call_count += 1
            return resp

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["items"]

        def is_last_page(resp: Response) -> bool:
            return resp.status_code == 204

        result = list(
            paginate_offset(
                fetch_page,
                extract_records,
                page_size=100,
                is_last_page=is_last_page,
            )
        )
        assert result == [[{"id": 1}], []]


class TestPaginatePage:
    def test_multi_page(self):
        pages = [
            _mock_response({"results": [{"id": i} for i in range(5)]}),
            _mock_response({"results": [{"id": 5}]}),
        ]
        call_count = 0

        def fetch_page(params: dict) -> Response:
            nonlocal call_count
            resp = pages[call_count]
            call_count += 1
            return resp

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["results"]

        result = list(paginate_page(fetch_page, extract_records, page_size=5))
        assert result == [
            [{"id": i} for i in range(5)],
            [{"id": 5}],
        ]

    def test_empty_first_page(self):
        pages = [_mock_response({"results": []})]

        def fetch_page(params: dict) -> Response:
            return pages[0]

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["results"]

        result = list(paginate_page(fetch_page, extract_records, page_size=5))
        assert result == [[]]

    def test_custom_param_names(self):
        pages = [_mock_response({"results": []})]
        captured_params: list[dict] = []

        def fetch_page(params: dict) -> Response:
            captured_params.append(params.copy())
            return pages[0]

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["results"]

        list(
            paginate_page(
                fetch_page,
                extract_records,
                page_size=100,
                page_param="p",
                size_param="per_page",
            )
        )
        assert captured_params[0]["p"] == 1
        assert captured_params[0]["per_page"] == 100

    def test_start_page(self):
        pages = [_mock_response({"results": []})]
        captured_params: list[dict] = []

        def fetch_page(params: dict) -> Response:
            captured_params.append(params.copy())
            return pages[0]

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()["results"]

        list(
            paginate_page(
                fetch_page, extract_records, page_size=10, start=0
            )
        )
        assert captured_params[0]["page"] == 0
```

- [ ] **Run tests to verify they fail**

Run: `uv run pytest tests/libraries/http/test_pagination.py -v` Expected: FAIL —
`ModuleNotFoundError: No module named 'teamster.libraries.http.pagination'`

### Step 3.2: Implement pagination helpers

- [ ] **Create pagination module**

```python
# src/teamster/libraries/http/pagination.py
from collections.abc import Callable, Iterator
from typing import Any

from requests import Response


def paginate_cursor(
    fetch_page: Callable[[dict], Response],
    extract_records: Callable[[Response], list[dict[str, Any]]],
    extract_cursor: Callable[[Response], str | None],
    page_params: dict | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Cursor-based pagination. Stops when extract_cursor returns None."""
    params = dict(page_params) if page_params else {}

    while True:
        response = fetch_page(params)
        records = extract_records(response)
        yield records

        cursor = extract_cursor(response)
        if cursor is None:
            break
        params["page[after]"] = cursor


def paginate_offset(
    fetch_page: Callable[[dict], Response],
    extract_records: Callable[[Response], list[dict[str, Any]]],
    page_size: int,
    start: int = 0,
    offset_param: str = "offset",
    limit_param: str = "limit",
    is_last_page: Callable[[Response], bool] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """Offset-based pagination. Stops when records < page_size or is_last_page."""
    offset = start

    while True:
        params = {offset_param: offset, limit_param: page_size}
        response = fetch_page(params)
        records = extract_records(response)
        yield records

        if is_last_page is not None and is_last_page(response):
            break
        if len(records) < page_size:
            break
        offset += page_size


def paginate_page(
    fetch_page: Callable[[dict], Response],
    extract_records: Callable[[Response], list[dict[str, Any]]],
    page_size: int,
    start: int = 1,
    page_param: str = "page",
    size_param: str = "pagesize",
) -> Iterator[list[dict[str, Any]]]:
    """Page-number pagination. Stops when records empty or < page_size."""
    page = start

    while True:
        params = {page_param: page, size_param: page_size}
        response = fetch_page(params)
        records = extract_records(response)
        yield records

        if len(records) == 0 or len(records) < page_size:
            break
        page += 1
```

- [ ] **Run tests to verify they pass**

Run: `uv run pytest tests/libraries/http/test_pagination.py -v` Expected: 12
passed

### Step 3.3: Commit

- [ ] **Commit pagination helpers**

```bash
git add src/teamster/libraries/http/pagination.py tests/libraries/http/test_pagination.py
git commit -m "feat(http): add cursor, offset, and page pagination helpers"
```

---

## Task 4: Migrate Tier 1 — SmartRecruitersResource

**Files:**

- Modify: `src/teamster/libraries/smartrecruiters/resources.py`

### Step 4.1: Write migration test

- [ ] **Add subclass test for SmartRecruitersResource**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.smartrecruiters.resources import SmartRecruitersResource


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
```

- [ ] **Run tests to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestSmartRecruitersResource -v`
Expected: FAIL — SmartRecruitersResource does not inherit BaseHTTPResource yet

### Step 4.2: Migrate SmartRecruitersResource

- [ ] **Rewrite the resource to inherit from BaseHTTPResource**

Replace the full contents of
`src/teamster/libraries/smartrecruiters/resources.py`:

```python
from teamster.libraries.http.resources import BaseHTTPResource


class SmartRecruitersResource(BaseHTTPResource):
    smart_token: str

    def _setup_session(self) -> None:
        self._base_url = "https://api.smartrecruiters.com"
        self._session.headers["X-SmartToken"] = self.smart_token
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestSmartRecruitersResource -v`
Expected: 3 passed

### Step 4.3: Commit

- [ ] **Commit SmartRecruiters migration**

```bash
git add -u
git commit -m "refactor(smartrecruiters): migrate to BaseHTTPResource"
```

---

## Task 5: Migrate Tier 1 — PowerSchoolEnrollmentResource

**Files:**

- Modify: `src/teamster/libraries/powerschool/enrollment/resources.py`

### Step 5.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.powerschool.enrollment.resources import (
    PowerSchoolEnrollmentResource,
)


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
```

- [ ] **Run to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestPowerSchoolEnrollmentResource -v`
Expected: FAIL

### Step 5.2: Migrate PowerSchoolEnrollmentResource

- [ ] **Rewrite the resource**

Replace the full contents of
`src/teamster/libraries/powerschool/enrollment/resources.py`:

```python
from typing import Any

from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class PowerSchoolEnrollmentResource(BaseHTTPResource):
    api_key: str
    api_version: str = "v1"
    page_size: int = 50

    def _setup_session(self) -> None:
        self._base_url = "https://registration.powerschool.com/api"
        self._session.auth = (self.api_key, "")

    def _get_url(self, *parts: str) -> str:
        return self._base_url + "/" + self.api_version + "/" + "/".join(parts)

    def list(self, endpoint: str, **kwargs) -> list[dict[str, Any]]:
        all_records: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(endpoint, params=params, **kwargs)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            response_json = resp.json()
            metadata, records = response_json.values()
            self._log.debug(metadata)
            return records

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=self.page_size,
            size_param="pagesize",
        ):
            all_records.extend(page_records)

        return all_records
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestPowerSchoolEnrollmentResource -v`
Expected: 3 passed

### Step 5.3: Commit

- [ ] **Commit PowerSchool Enrollment migration**

```bash
git add -u
git commit -m "refactor(powerschool): migrate enrollment resource to BaseHTTPResource"
```

---

## Task 6: Migrate Tier 1 — OvergradResource

**Files:**

- Modify: `src/teamster/libraries/overgrad/resources.py`

### Step 6.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.overgrad.resources import OvergradResource


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
            resource._get_url("students")
            == "https://api.overgrad.com/api/v1/students"
        )

    def test_get_url_with_extra_parts(self):
        resource = self._make()
        assert (
            resource._get_url("students", "123")
            == "https://api.overgrad.com/api/v1/students/123"
        )
```

- [ ] **Run to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestOvergradResource -v`
Expected: FAIL

### Step 6.2: Migrate OvergradResource

- [ ] **Rewrite the resource**

Replace the full contents of `src/teamster/libraries/overgrad/resources.py`:

```python
from typing import Any

from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class OvergradResource(BaseHTTPResource):
    api_key: str
    api_version: str = "v1"
    page_limit: int = 20

    def _setup_session(self) -> None:
        self._base_url = "https://api.overgrad.com/api"
        self._session.headers["ApiKey"] = self.api_key

    def _get_url(self, *parts: str) -> str:
        return self._base_url + "/" + self.api_version + "/" + "/".join(parts)

    def list(self, path: str, *args: str, **kwargs) -> list[dict[str, Any]]:
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(path, *args, params=params, **kwargs)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            response_json = resp.json()
            self._log.debug(
                {k: v for k, v in response_json.items() if k != "data"}
            )
            return response_json["data"]

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=self.page_limit,
            page_param="page",
            size_param="limit",
        ):
            all_data.extend(page_records)

        return all_data
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestOvergradResource -v`
Expected: 3 passed

### Step 6.3: Commit

- [ ] **Commit Overgrad migration**

```bash
git add -u
git commit -m "refactor(overgrad): migrate to BaseHTTPResource"
```

---

## Task 7: Migrate Tier 1 — KnowBe4Resource

**Files:**

- Modify: `src/teamster/libraries/knowbe4/resources.py`

### Step 7.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.knowbe4.resources import KnowBe4Resource


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
        assert "us.api.knowbe4.com" in resource._base_url
```

- [ ] **Run to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestKnowBe4Resource -v`
Expected: FAIL

### Step 7.2: Migrate KnowBe4Resource

- [ ] **Rewrite the resource**

Replace the full contents of `src/teamster/libraries/knowbe4/resources.py`:

```python
from typing import Any

from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class KnowBe4Resource(BaseHTTPResource):
    api_key: str
    server: str
    page_size: int = 100

    def _setup_session(self) -> None:
        self._base_url = f"https://{self.server}.api.knowbe4.com"
        self._session.headers["Authorization"] = f"Bearer {self.api_key}"

    def _get_url(self, *parts: str) -> str:
        return self._base_url + "/v1/" + "/".join(parts)

    def list(self, resource: str, **kwargs) -> list[dict[str, Any]]:
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(resource, params=params)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=self.page_size,
            page_param="page",
            size_param="per_page",
        ):
            all_data.extend(page_records)

        return all_data
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestKnowBe4Resource -v`
Expected: 3 passed

### Step 7.3: Run all tests and commit

- [ ] **Run full test suite for http module**

Run: `uv run pytest tests/libraries/http/ -v` Expected: All passed

- [ ] **Commit KnowBe4 migration**

```bash
git add -u
git commit -m "refactor(knowbe4): migrate to BaseHTTPResource"
```

---

## Task 8: Migrate Tier 2 — ZendeskResource

**Files:**

- Modify: `src/teamster/libraries/zendesk/resources.py`

### Step 8.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.zendesk.resources import ZendeskResource


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
        assert (
            resource._get_url("tickets")
            == "https://test.zendesk.com/api/v2/tickets"
        )

    def test_get_retry_after_parses_ratelimit_remaining(self):
        resource = self._make()
        resp = _make_error_response(429)
        resp.headers["ratelimit-remaining"] = "0"
        resp.headers["ratelimit-reset"] = str(time.time() + 5)
        result = resource._get_retry_after(resp)
        assert result is not None
        assert result > 0
```

Add `import time` to the top-level imports if not already present.

- [ ] **Run to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestZendeskResource -v`
Expected: FAIL

### Step 8.2: Migrate ZendeskResource

- [ ] **Rewrite the resource**

Replace the full contents of `src/teamster/libraries/zendesk/resources.py`:

```python
import time
from typing import Any

from requests import Response
from requests.auth import HTTPBasicAuth

from teamster.libraries.http.pagination import paginate_cursor
from teamster.libraries.http.resources import BaseHTTPResource


class ZendeskResource(BaseHTTPResource):
    subdomain: str
    email: str
    token: str
    page_size: int = 100
    api_version: str = "v2"

    def _setup_session(self) -> None:
        self._base_url = f"https://{self.subdomain}.zendesk.com/api"
        self._session.headers["Content-Type"] = "application/json"
        self._session.auth = HTTPBasicAuth(
            username=f"{self.email}/token", password=self.token
        )

    def _get_url(self, *parts: str) -> str:
        return (
            self._base_url
            + "/"
            + self.api_version
            + "/"
            + "/".join(str(p) for p in parts if p)
        )

    def _get_retry_after(self, response: Response) -> float | None:
        """Parse Zendesk-specific rate-limit headers."""
        remaining = response.headers.get("ratelimit-remaining")
        if remaining is not None and int(remaining) <= 0:
            reset = response.headers.get("ratelimit-reset", "60")
            return float(reset) - time.time() + 1

        endpoint_header = response.headers.get("Zendesk-RateLimit-Endpoint", "")
        if endpoint_header:
            parts = endpoint_header.split(";")
            if int(parts[1].split("=")[1]) <= 0:
                return float(parts[2].split("=")[1]) - time.time() + 1

        return super()._get_retry_after(response)

    def list(self, resource: str, **kwargs) -> list[dict[str, Any]]:
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(resource, params=params)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()[resource]

        def extract_cursor(resp: Response) -> str | None:
            meta = resp.json().get("meta", {})
            if meta.get("has_more"):
                return meta.get("after_cursor")
            return None

        for page_records in paginate_cursor(
            fetch_page,
            extract_records,
            extract_cursor,
            page_params={"page[size]": self.page_size, **kwargs.get("params", {})},
        ):
            all_data.extend(page_records)

        return all_data
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestZendeskResource -v`
Expected: 4 passed

### Step 8.3: Commit

- [ ] **Commit Zendesk migration**

```bash
git add -u
git commit -m "refactor(zendesk): migrate to BaseHTTPResource with custom rate-limit parsing"
```

---

## Task 9: Migrate Tier 2 — CoupaResource

**Files:**

- Modify: `src/teamster/libraries/coupa/resources.py`

### Step 9.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.coupa.resources import CoupaResource


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
        # Patch OAuth2 token fetch to avoid real HTTP call
        with patch(
            "teamster.libraries.coupa.resources.OAuth2Session"
        ) as mock_oauth:
            mock_session = MagicMock()
            mock_session.fetch_token.return_value = {"access_token": "test-token"}
            mock_session.headers = {}
            mock_oauth.return_value = mock_session
            resource.setup_for_execution(ctx)
        return resource

    def test_setup_sets_bearer_header(self):
        resource = self._make()
        assert "Bearer" in resource._session.headers.get("Authorization", "")

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("purchase_orders")
            == "https://test.coupahost.com/api/purchase_orders"
        )
```

- [ ] **Run to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestCoupaResource -v`
Expected: FAIL

### Step 9.2: Migrate CoupaResource

- [ ] **Rewrite the resource**

Replace the full contents of `src/teamster/libraries/coupa/resources.py`:

```python
from typing import Any, cast

from oauthlib.oauth2 import BackendApplicationClient
from requests import Response
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from teamster.libraries.http.pagination import paginate_offset
from teamster.libraries.http.resources import BaseHTTPResource


class CoupaResource(BaseHTTPResource):
    instance_url: str
    client_id: str
    client_secret: str
    scope: list[str]

    def _setup_session(self) -> None:
        self._base_url = f"https://{self.instance_url}"

        # trunk-ignore(pyright/reportArgumentType): scope is list[str], API expects str
        self._session = OAuth2Session(
            client=BackendApplicationClient(client_id=self.client_id, scope=self.scope)
        )

        token_dict = self._session.fetch_token(
            token_url=f"{self._base_url}/oauth2/token",
            auth=HTTPBasicAuth(username=self.client_id, password=self.client_secret),
        )

        self._session.headers["Authorization"] = (
            "Bearer " + token_dict["access_token"]
        )
        self._session.headers["Accept"] = "application/json"

    @property
    def oauth_session(self) -> OAuth2Session:
        return cast(OAuth2Session, self._session)

    def _get_url(self, *parts: str) -> str:
        return self._base_url + "/api/" + "/".join(parts)

    def list(self, resource: str, **kwargs) -> list[dict[str, Any]]:
        all_data: list[dict[str, Any]] = []

        def fetch_page(params: dict) -> Response:
            return self.get(resource, params=params, **kwargs)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()

        for page_records in paginate_offset(
            fetch_page, extract_records, page_size=50
        ):
            all_data.extend(page_records)

        return all_data
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestCoupaResource -v`
Expected: 2 passed

### Step 9.3: Commit

- [ ] **Commit Coupa migration**

```bash
git add -u
git commit -m "refactor(coupa): migrate to BaseHTTPResource with OAuth2Session"
```

---

## Task 10: Migrate Tier 2 — GrowResource

**Files:**

- Modify: `src/teamster/libraries/level_data/grow/resources.py`

### Step 10.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.level_data.grow.resources import GrowResource


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
        assert "Bearer test-token" in resource._session.headers.get(
            "Authorization", ""
        )

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
```

- [ ] **Run to verify they fail**

Run: `uv run pytest tests/libraries/http/test_resources.py::TestGrowResource -v`
Expected: FAIL

### Step 10.2: Migrate GrowResource

- [ ] **Rewrite the resource**

Replace the full contents of
`src/teamster/libraries/level_data/grow/resources.py`:

```python
import copy
from typing import Any

from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response
from requests_oauthlib import OAuth2Session

from teamster.libraries.http.pagination import paginate_offset
from teamster.libraries.http.resources import BaseHTTPResource


class GrowResource(BaseHTTPResource):
    client_id: str
    client_secret: str
    district_id: str
    api_response_limit: int = 100

    _default_params: dict = PrivateAttr()

    def _setup_session(self) -> None:
        self._base_url = "https://grow-api.leveldata.com"

        self._default_params = {
            "limit": self.api_response_limit,
            "district": self.district_id,
            "skip": 0,
        }

        oauth = OAuth2Session(
            client=BackendApplicationClient(client_id=self.client_id)
        )
        token_dict = oauth.fetch_token(
            token_url=f"{self._base_url}/auth/client/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token_dict['access_token']}",
            }
        )

    def _get_url(self, *parts: str) -> str:
        return self._base_url + "/external/" + "/".join(parts)

    def get(self, endpoint: str, *args: str, **kwargs) -> dict[str, Any]:
        """GET with pagination and response validation.

        Args:
            endpoint: API endpoint name.
            *args: If provided, treated as resource ID for single-resource fetch.
            **kwargs: Additional params merged into default params.
        """
        params = copy.deepcopy(self._default_params)
        params.update(kwargs)

        if args:
            self._log.debug(f"GET: {self._get_url(endpoint, *args)}")
            response = self._request(
                "GET", self._get_url(endpoint, *args), params=params
            )
            response_json = response.json()
            return {
                "count": 1,
                "limit": self._default_params["limit"],
                "skip": self._default_params["skip"],
                "data": [response_json],
            }

        data: list[dict[str, Any]] = []

        def fetch_page(page_params: dict) -> Response:
            merged = {**params, **page_params}
            self._log.debug(f"GET: {self._get_url(endpoint)}\nPARAMS: {merged}")
            return self._request("GET", self._get_url(endpoint), params=merged)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            response_json = resp.json()
            if "data" not in response_json:
                self._log.error(msg="Missing 'data' key in response")
                return []
            return response_json["data"]

        count = 0
        for page_records in paginate_offset(
            fetch_page,
            extract_records,
            page_size=self.api_response_limit,
            offset_param="skip",
            limit_param="limit",
        ):
            if not page_records and count > 0:
                raise Exception("API returned an incomplete response")
            data.extend(page_records)
            self._log.debug(f"{len(data)}/{count} records")
            # Update count from latest response — fetch_page stores it
            # We need to get count from the response; restructure slightly
            count = max(count, len(data))

        # Reconstruct the response format Grow assets expect
        return {
            "count": len(data),
            "limit": self._default_params["limit"],
            "skip": self._default_params["skip"],
            "data": data,
        }

    def post(self, endpoint: str, *args: str, **kwargs) -> dict[str, Any]:
        url = self._get_url(endpoint, *args)
        self._log.debug(f"POST: {url}")
        return self._request("POST", url, **kwargs).json()

    def put(self, endpoint: str, *args: str, **kwargs) -> dict[str, Any]:
        url = self._get_url(endpoint, *args)
        self._log.debug(f"PUT: {url}")
        return self._request("PUT", url, **kwargs).json()

    def delete(self, endpoint: str, *args: str) -> dict[str, Any]:
        url = self._get_url(endpoint, *args)
        self._log.debug(f"DELETE: {url}")
        return self._request("DELETE", url).json()
```

Note: Grow's `get()` has custom pagination with response validation that doesn't
map cleanly to the generic paginator. The count comes from the response JSON and
the paginator doesn't naturally expose it. This implementation uses
`paginate_offset` for the loop mechanics but handles the count validation in the
`get()` wrapper. The implementer should verify this against the actual Grow API
response shape — the `count` field in the first page's response tells the total;
if pagination completes but `len(data) != count`, it's an error. The implementer
may need to refine this by tracking count in a closure variable within
`extract_records`.

- [ ] **Run tests to verify they pass**

Run: `uv run pytest tests/libraries/http/test_resources.py::TestGrowResource -v`
Expected: 3 passed

### Step 10.3: Commit

- [ ] **Commit Grow migration**

```bash
git add -u
git commit -m "refactor(grow): migrate to BaseHTTPResource with offset pagination"
```

---

## Task 11: Migrate Tier 3 — AdpWorkforceNowResource

**Files:**

- Modify: `src/teamster/libraries/adp/workforce_now/api/resources.py`

### Step 11.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.adp.workforce_now.api.resources import (
    AdpWorkforceNowResource,
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
        assert "Bearer" in resource._session.headers.get("Authorization", "")

    def test_setup_sets_cert(self):
        resource = self._make()
        assert resource._session.cert == ("/tmp/cert.pem", "/tmp/key.pem")

    def test_get_url(self):
        resource = self._make()
        assert (
            resource._get_url("hr", "v2", "workers")
            == "https://api.adp.com/hr/v2/workers"
        )

    def test_post_url_pattern(self):
        resource = self._make()
        with patch.object(resource, "_request") as mock:
            mock.return_value = MagicMock(status_code=200)
            resource.post_action("hr/v2/workers", "request", "submit", payload={})
            mock.assert_called_once_with(
                "POST",
                "https://api.adp.com/hr/v2/workers.request.submit",
                json={},
            )
```

- [ ] **Run to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestAdpWorkforceNowResource -v`
Expected: FAIL

### Step 11.2: Migrate AdpWorkforceNowResource

- [ ] **Rewrite the resource**

Replace the full contents of
`src/teamster/libraries/adp/workforce_now/api/resources.py`:

```python
from typing import Any, cast

from oauthlib.oauth2 import BackendApplicationClient
from pydantic import PrivateAttr
from requests import Response
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from teamster.libraries.http.pagination import paginate_offset
from teamster.libraries.http.resources import BaseHTTPResource


class AdpWorkforceNowResource(BaseHTTPResource):
    client_id: str
    client_secret: str
    cert_filepath: str
    key_filepath: str
    masked: bool = True

    def _setup_session(self) -> None:
        self._base_url = "https://api.adp.com"

        self._session = OAuth2Session(
            client=BackendApplicationClient(client_id=self.client_id)
        )
        self._session.cert = (self.cert_filepath, self.key_filepath)

        token_dict = self._session.fetch_token(
            # trunk-ignore(bandit/B106): token URL, not a password
            token_url="https://accounts.adp.com/auth/oauth/v2/token",
            auth=HTTPBasicAuth(
                username=self.client_id, password=self.client_secret
            ),
        )

        self._session.headers["Authorization"] = (
            f"Bearer {token_dict.get('access_token')}"
        )

        if not self.masked:
            self._session.headers["Accept"] = "application/json;masked=false"

    @property
    def oauth_session(self) -> OAuth2Session:
        return cast(OAuth2Session, self._session)

    def post_action(
        self, endpoint: str, subresource: str, verb: str, payload: dict
    ) -> Response:
        """ADP-specific POST URL pattern: {endpoint}.{subresource}.{verb}."""
        return self._request(
            "POST",
            f"{self._base_url}/{endpoint}.{subresource}.{verb}",
            json=payload,
        )

    def get_records(
        self, endpoint: str, params: dict | None = None
    ) -> list[dict[str, Any]]:
        endpoint_name = endpoint.split("/")[-1]

        if params is None:
            params = {}

        all_records: list[dict[str, Any]] = []

        def fetch_page(page_params: dict) -> Response:
            merged = {**params, **page_params}
            self._log.debug(msg=merged)
            return self.get(endpoint, params=merged)

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            return resp.json()[endpoint_name]

        def is_last_page(resp: Response) -> bool:
            return resp.status_code == 204

        for page_records in paginate_offset(
            fetch_page,
            extract_records,
            page_size=100,
            offset_param="$skip",
            limit_param="$top",
            is_last_page=is_last_page,
        ):
            all_records.extend(page_records)

        return all_records
```

Note: The existing `post()` method is renamed to `post_action()` to avoid
conflicting with the base class `post()`. The implementer must update these four
callers from `.post(` to `.post_action(`:

- `src/teamster/code_locations/kipptaf/adp/workforce_now/api/assets.py:121`
- `src/teamster/code_locations/kipptaf/adp/workforce_now/api/assets.py:148`
- `src/teamster/libraries/adp/workforce_now/api/ops.py:47`
- `src/teamster/libraries/adp/workforce_now/api/ops.py:71`

- [ ] **Check for callers of the old `post()` method and update them**

Run:
`uv run grep -rn '\.post(' src/teamster/code_locations/kipptaf/adp/ src/teamster/libraries/adp/workforce_now/api/assets.py`

Update any callers from `.post(endpoint, subresource, verb, payload)` to
`.post_action(endpoint, subresource, verb, payload=payload)`.

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestAdpWorkforceNowResource -v`
Expected: 4 passed

### Step 11.3: Commit

- [ ] **Commit ADP WFN migration**

```bash
git add -u
git commit -m "refactor(adp): migrate workforce_now resource to BaseHTTPResource with mTLS and offset pagination"
```

---

## Task 12: Migrate Tier 3 — DeansListResource

**Files:**

- Modify: `src/teamster/libraries/deanslist/resources.py`

### Step 12.1: Write migration test

- [ ] **Add subclass test**

Append to `tests/libraries/http/test_resources.py`:

```python
from teamster.libraries.deanslist.resources import DeansListResource


class TestDeansListResource:
    def _make(self) -> DeansListResource:
        resource = DeansListResource(
            subdomain="test-district",
            api_key_map="/tmp/fake-key-map.yaml",
        )
        ctx = MagicMock()
        ctx.log = MagicMock()
        with patch(
            "builtins.open",
            MagicMock(
                return_value=MagicMock(
                    __enter__=MagicMock(
                        return_value=MagicMock(
                            read=MagicMock(
                                return_value="api_key_map:\n  100: key-100\n  200: key-200"
                            )
                        )
                    ),
                    __exit__=MagicMock(return_value=False),
                )
            ),
        ):
            resource.setup_for_execution(ctx)
        return resource

    def test_base_url(self):
        resource = self._make()
        assert (
            resource._base_url
            == "https://test-district.deanslistsoftware.com/api"
        )

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
```

- [ ] **Run to verify they fail**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestDeansListResource -v`
Expected: FAIL

### Step 12.2: Migrate DeansListResource

- [ ] **Rewrite the resource**

Replace the full contents of `src/teamster/libraries/deanslist/resources.py`:

```python
import pathlib
from typing import Any

import fastavro
import fastavro.types
import yaml
from pydantic import PrivateAttr
from requests import Response

from teamster.libraries.http.pagination import paginate_page
from teamster.libraries.http.resources import BaseHTTPResource


class DeansListResource(BaseHTTPResource):
    subdomain: str
    api_key_map: str

    _api_key_map: dict = PrivateAttr()
    _current_school_id: int = PrivateAttr(default=0)

    def _setup_session(self) -> None:
        self._base_url = f"https://{self.subdomain}.deanslistsoftware.com/api"

        with open(self.api_key_map) as f:
            self._api_key_map = yaml.safe_load(f)["api_key_map"]

    def _get_url(self, *parts: str) -> str:
        """DeansList URL construction.

        Args:
            *parts: (api_version, endpoint, *extra_parts).
                Beta endpoints use PHP export format with -data suffix for
                behavior, homework, comm.
        """
        if len(parts) < 2:
            return self._base_url + "/" + "/".join(parts)

        api_version, endpoint, *extra = parts

        if api_version == "beta":
            suffix = "-data" if endpoint in ("behavior", "homework", "comm") else ""
            return (
                f"{self._base_url}/{api_version}/export/get-{endpoint}{suffix}.php"
            )

        if extra:
            return f"{self._base_url}/{api_version}/{endpoint}/{'/'.join(extra)}"
        return f"{self._base_url}/{api_version}/{endpoint}"

    def _prepare_request(
        self, method: str, url: str, kwargs: dict
    ) -> tuple[str, str, dict]:
        """Inject school-specific API key into params."""
        if self._current_school_id:
            params = kwargs.setdefault("params", {})
            params["apikey"] = self._api_key_map[self._current_school_id]
        return method, url, kwargs

    def _request(self, method: str, url: str, **kwargs) -> Response:
        """Override to strip apikey from params after request (avoid logging)."""
        response = super()._request(method, url, **kwargs)
        params = kwargs.get("params", {})
        params.pop("apikey", None)
        return response

    def get(
        self,
        api_version: str,
        endpoint: str,
        school_id: int,
        params: dict,
        *args: str,
        **kwargs,
    ) -> tuple[int, list[dict[str, Any]]]:
        self._current_school_id = school_id
        self._log.info(
            f"GET:\t{self._get_url(api_version, endpoint, *args)}"
            f"\nSCHOOL_ID:\t{school_id}\nPARAMS:\t{params}"
        )

        url = self._get_url(api_version, endpoint, *args)
        response = super()._request("GET", url, params=params, **kwargs)
        response_json: dict = response.json()

        total_row_count = response_json.get("rowcount", 0) + response_json.get(
            "deleted_rowcount", 0
        )

        data = response_json.get("data", [])
        if isinstance(data, dict):
            data = [data]
            total_row_count = 1

        deleted_data = response_json.get("deleted_data", [])
        for d in deleted_data:
            d["is_deleted"] = True

        all_data = data + deleted_data
        self._current_school_id = 0
        return total_row_count, all_data

    def list(
        self,
        api_version: str,
        endpoint: str,
        school_id: int,
        params: dict,
        page_size: int = 250000,
        avro_schema: fastavro.types.Schema | None = None,
        *args: str,
        **kwargs,
    ) -> tuple[int, list[dict[str, Any]] | pathlib.Path]:
        self._current_school_id = school_id

        data_filepath = pathlib.Path(
            f"env/deanslist/{endpoint}/{params['UpdatedSince']}/{school_id}/data.avro"
        ).absolute()

        url = self._get_url(api_version, endpoint, *args)

        all_data: list[dict[str, Any]] = []
        total_count = 0

        if avro_schema is not None:
            data_filepath.parent.mkdir(parents=True, exist_ok=True)
            with data_filepath.open("wb") as fo:
                fastavro.writer(
                    fo=fo,
                    schema=avro_schema,
                    records=[],
                    codec="snappy",
                    strict_allow_default=True,
                )

        fo = data_filepath.open("a+b") if avro_schema is not None else None

        def fetch_page(page_params: dict) -> Response:
            merged = {**params, **page_params}
            return super(DeansListResource, self)._request(
                "GET", url, params=merged, **kwargs
            )

        def extract_records(resp: Response) -> list[dict[str, Any]]:
            nonlocal total_count
            response_json = resp.json()
            total_count = response_json["total_count"]
            return response_json["data"]

        for page_records in paginate_page(
            fetch_page,
            extract_records,
            page_size=page_size,
            page_param="page",
            size_param="page_size",
        ):
            if avro_schema is not None and fo is not None:
                fastavro.writer(
                    fo=fo,
                    schema=avro_schema,
                    records=page_records,
                    codec="snappy",
                    strict_allow_default=True,
                )
            else:
                all_data.extend(page_records)

        if fo is not None:
            fo.close()

        self._current_school_id = 0

        if avro_schema is not None:
            return int(total_count), data_filepath
        return int(total_count), all_data
```

- [ ] **Run tests to verify they pass**

Run:
`uv run pytest tests/libraries/http/test_resources.py::TestDeansListResource -v`
Expected: 5 passed

### Step 12.3: Commit

- [ ] **Commit DeansList migration**

```bash
git add -u
git commit -m "refactor(deanslist): migrate to BaseHTTPResource with school_id injection and beta URL logic"
```

---

## Task 13: Final validation and cleanup

**Files:**

- Modify: `tests/libraries/http/test_resources.py` (lint cleanup)

### Step 13.1: Run full test suite

- [ ] **Run all http module tests**

Run: `uv run pytest tests/libraries/http/ -v` Expected: All passed

### Step 13.2: Lint

- [ ] **Run trunk check on all changed files**

```bash
/workspaces/teamster/.trunk/tools/trunk check src/teamster/libraries/http/ tests/libraries/http/ src/teamster/libraries/smartrecruiters/resources.py src/teamster/libraries/powerschool/enrollment/resources.py src/teamster/libraries/overgrad/resources.py src/teamster/libraries/knowbe4/resources.py src/teamster/libraries/zendesk/resources.py src/teamster/libraries/coupa/resources.py src/teamster/libraries/level_data/grow/resources.py src/teamster/libraries/adp/workforce_now/api/resources.py src/teamster/libraries/deanslist/resources.py
```

Fix any lint issues found.

### Step 13.3: Definition validation reminder

- [ ] **Ask user to validate Dagster definitions**

The implementer cannot run `dagster definitions validate` in Claude sessions
(env vars blocked by hooks). Ask someone with access to run:

```bash
set -a && source env/.env && set +a
uv run dagster definitions validate --module teamster.code_locations.kipptaf.definitions
uv run dagster definitions validate --module teamster.code_locations.kippnewark.definitions
uv run dagster definitions validate --module teamster.code_locations.kippcamden.definitions
uv run dagster definitions validate --module teamster.code_locations.kippmiami.definitions
```

All four must pass. kipptaf exercises 7 of 9 resources; kippnewark/kippcamden
exercise DeansList + Overgrad; kippmiami exercises DeansList.

### Step 13.4: Final commit

- [ ] **Commit any lint fixes**

```bash
git add -u
git commit -m "style(http): lint cleanup"
```
