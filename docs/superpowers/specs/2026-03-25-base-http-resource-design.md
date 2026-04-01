# Base HTTP Resource Extraction

**Issue:** [#3390](https://github.com/TEAMSchools/teamster/issues/3390)
**Date:** 2026-03-25

## Problem

14 `ConfigurableResource` classes independently implement the same
`requests.Session` wrapper pattern, duplicating session lifecycle, URL
construction, request wrapping, error handling, and auth setup. This makes it
hard to add cross-cutting improvements (retries, rate limiting, metrics) and
increases the cost of adding new API integrations. Of these, 10 are actively
used in code locations; 4 are vestigial (builder functions exist but are not
called).

## Approach

Hook-based single-inheritance base class. Each subclass overrides only what it
needs — auth setup, URL format, error handling, or request preparation. The base
provides built-in retry via tenacity, standardized error handling with
rate-limit awareness, and pagination helpers for the three common patterns.

Vestigial resource libraries (AdpWorkforceManagerResource, MClassResource,
DibelsDataSystemResource, CouchdropResource, AlchemerResource) are preserved
untouched — their builder functions exist but are not called by any code
location. Proactive rate-limiting sleeps in existing resources (Overgrad,
KnowBe4, ADP WFN) are removed during migration; tenacity retry on 429 is
sufficient.

## Base Class Design

### Location

`src/teamster/libraries/http/resources.py`

### Config Fields

| Field             | Type    | Default | Purpose                          |
| ----------------- | ------- | ------- | -------------------------------- |
| `request_timeout` | `float` | `60.0`  | Default timeout for all requests |

Subclasses add their own config fields (credentials, subdomain, etc.) via normal
Dagster `ConfigurableResource` config.

### PrivateAttrs

**`_session` typing:** The base class types `_session` as `Session`.
OAuth2Session subclasses (Coupa, ADP WFN) assign an `OAuth2Session` in
`_setup_session()` — this works at runtime since `OAuth2Session` extends
`Session`, but pyright may flag it. Subclasses that need
`OAuth2Session`-specific methods (e.g., `fetch_token()`) add a typed property
accessor with `cast`:

```python
@property
def oauth_session(self) -> OAuth2Session:
    return cast(OAuth2Session, self._session)
```

This matches the existing codebase pattern (Coupa/ADP already assign
`OAuth2Session` to a `Session`-typed attr), avoids Dagster/Pydantic generic
compatibility risk, and limits the cast to one accessor per subclass.

| Field       | Type                | Default                   | Purpose                               |
| ----------- | ------------------- | ------------------------- | ------------------------------------- |
| `_session`  | `Session`           | `default_factory=Session` | Shared HTTP session (see note above)  |
| `_base_url` | `str`               | —                         | Set by subclass in `_setup_session()` |
| `_log`      | `DagsterLogManager` | —                         | Assigned in `setup_for_execution()`   |

### Lifecycle

- **`setup_for_execution(context: InitResourceContext)`** — assigns `_log` via
  `check.not_none(value=context.log)` (using `dagster_shared.check`, matching
  existing resource convention), then calls `_setup_session()`. Subclasses never
  override this; they override `_setup_session()` instead.
- **`teardown_after_execution(context: InitResourceContext)`** — calls
  `_session.close()`. This is net-new behavior (no existing resource implements
  teardown), added to prevent session leaks. Subclasses can call `super()` for
  additional cleanup.

Note: if a tenacity retry is in-flight when Dagster cancels a run,
`teardown_after_execution` will not interrupt it (same thread). At the current
config (3 attempts, 60s max wait) this is acceptable — revisit if retry
parameters grow more aggressive.

### Request Pipeline

The core request flow is:

```text
_request(method, url, **kwargs)
  → method, url, kwargs = _prepare_request(method, url, kwargs)
  → response = _session.request(method, url, **kwargs)
  → response.raise_for_status()
  → return response
  on HTTPError:
  → _handle_error(response, error)
```

#### `_request(method, url, **kwargs) -> Response`

The core method, decorated with tenacity `@retry`:

- `stop=stop_after_attempt(3)`
- `wait=wait_exponential_jitter(initial=1, max=60)`
- `retry=retry_if_exception_type(HTTPError)`

Subclasses can override retry behavior by re-decorating `_request` with a new
`@retry` decorator.

Logging levels are standardized across the request pipeline:

| Level     | Where           | Content                                    |
| --------- | --------------- | ------------------------------------------ |
| **info**  | `_request`      | Method, URL, status code, elapsed time     |
| **debug** | `_request`      | Request/response details (headers, params) |
| **error** | `_handle_error` | Method, URL, status code, `response.text`  |

#### `_prepare_request(method, url, kwargs) -> tuple[str, str, dict]`

Pre-request hook. Receives the method, URL, and kwargs dict; returns a (method,
url, kwargs) tuple that `_request` destructures and passes to
`_session.request()`. Default returns them unchanged. Subclasses override to
inject params, headers, or modify the request before it fires.

Example: DeansListResource injects `school_id` into `kwargs["params"]`.

#### `_handle_error(response, error) -> None`

Error hook called on HTTPError. Built-in defaults:

| Status    | Behavior                                                                                        |
| --------- | ----------------------------------------------------------------------------------------------- |
| **429**   | Calls `_get_retry_after(response)` for wait time, sleeps if found, raises to let tenacity retry |
| **401**   | Calls `_reauthenticate()` (once per request — see guard below), raises to let tenacity retry    |
| **5xx**   | Raises to let tenacity retry (exponential backoff)                                              |
| **Other** | Logs `response.text` at error level, re-raises                                                  |

Subclasses override for additional cases (e.g., Zendesk's custom rate-limit
headers, APIs that misuse 403 for expired tokens).

#### `_get_retry_after(response) -> float | None`

Parses rate-limit wait time from the response. Default checks in order:

1. `Retry-After` header — tries integer seconds first, then parses HTTP-date
   format via `email.utils.parsedate_to_datetime` and converts to delta
2. `X-RateLimit-Reset` header (epoch timestamp, converted to delta)
3. Returns `None` (falls back to tenacity's exponential backoff)

Subclasses override for non-standard formats: custom headers, response body
JSON, or computed delays.

#### `_reauthenticate() -> None`

Called by `_handle_error` on 401. Default re-raises the original `HTTPError` (no
re-auth capability). Subclasses override with refresh token or token re-fetch
logic; after re-authenticating, the override should return normally and let
tenacity retry the request.

**Single-attempt guard:** `_request` tracks whether `_reauthenticate()` has
already been called for the current request (via a flag reset at the top of each
`_request` call). On a second 401 for the same request, `_handle_error` skips
`_reauthenticate()` and re-raises immediately, preventing credential-loop
retries from burning all attempts.

### URL Construction

#### `_get_url(*parts: str) -> str`

Joins `_base_url` with path segments via `/`. Subclasses override when URL
structure differs (API version in path, endpoint format quirks).

### Convenience Methods

`get(*parts, **kwargs)`, `post(*parts, **kwargs)`, `put(*parts, **kwargs)`,
`delete(*parts, **kwargs)` — all delegate to
`_request(method, self._get_url(*parts), **kwargs)`.

## Pagination Helpers

Three methods on `BaseHTTPResource` that subclasses call from their `list()`
methods. These are utility methods that handle the loop mechanics while
delegating page-fetching to the subclass via callbacks.

All return `Iterator[list[dict[str, Any]]]` — yields per-page, so callers can
stream or collect as needed.

Each paginator takes two callbacks:

- `fetch_page(params) -> Response` — makes the HTTP request with the given
  pagination params
- `extract_records(response) -> list[dict[str, Any]]` — extracts the record list
  from the response (e.g., `response.json()["data"]`). This keeps response-shape
  knowledge in the subclass, not the paginator.

### `_paginate_cursor(fetch_page, extract_records, extract_cursor, page_params=None)`

- `extract_cursor(response) -> str | None` — pulls next cursor; `None` to stop
- Yields each page's records via `extract_records`
- **Consumers:** Zendesk, Finalsite

### `_paginate_offset(fetch_page, extract_records, page_size, start=0, offset_param="offset", limit_param="limit")`

- Increments offset by `page_size` each iteration
- Stops when `extract_records` returns fewer records than `page_size` (or empty)
- Supports custom stop condition via optional `is_last_page(response) -> bool`
  callback — default checks record count < page_size. ADP WFN overrides to stop
  on HTTP 204.
- **Consumers:** Grow, Coupa, ADP WFN (`$skip`/`$top`)

### `_paginate_page(fetch_page, extract_records, page_size, start=1, page_param="page", size_param="pagesize")`

- Increments page number each iteration
- Stops when `extract_records` returns empty or fewer than `page_size`
- **Consumers:** KnowBe4, PowerSchool, Overgrad, DeansList

## Migration Tiers

**`_request` signature normalization:** Several existing resources use
domain-specific `_request` signatures (e.g., KnowBe4's
`(method, resource, id, **kwargs)`, DeansList's
`(method, url, school_id, params, **kwargs)`). All must be refactored to the
base class's generic `(method, url, **kwargs)` signature, moving domain logic
into `_get_url()` or `_prepare_request()` overrides.

### Tier 1 — Direct drop-in (4 resources)

Override `_setup_session()` only, optionally `_get_url()`.

| Resource                      | Auth                  | Pagination       |
| ----------------------------- | --------------------- | ---------------- |
| SmartRecruitersResource       | `X-SmartToken` header | None             |
| PowerSchoolEnrollmentResource | Basic auth            | `_paginate_page` |
| OvergradResource              | `ApiKey` header       | `_paginate_page` |
| KnowBe4Resource               | Bearer header         | `_paginate_page` |

### Tier 2 — Additional hooks (4 resources)

Uses `_get_retry_after` override, OAuth2Session, or non-trivial
`_setup_session`.

| Resource          | Auth               | Pagination         | Hook overrides                                                                                     |
| ----------------- | ------------------ | ------------------ | -------------------------------------------------------------------------------------------------- |
| ZendeskResource   | HTTPBasicAuth      | `_paginate_cursor` | `_get_retry_after` parses `ratelimit-remaining`, `ratelimit-reset`, `Zendesk-RateLimit-Endpoint`   |
| FinalsiteResource | JWT bearer         | `_paginate_cursor` | Replaces recursive 429 retry with tenacity + `_get_retry_after` (behavior change: bounded retries) |
| CoupaResource     | OAuth2Session      | `_paginate_offset` | `_setup_session` assigns OAuth2Session                                                             |
| GrowResource      | OAuth2 token fetch | `_paginate_offset` | `extract_records` validates `data`/`count` keys; post-pagination assertion `len(results) == count` |

### Tier 3 — Complex (2 resources)

| Resource                | Auth                 | Pagination                                        | Hook overrides                                                                                                             |
| ----------------------- | -------------------- | ------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| AdpWorkforceNowResource | OAuth2Session + mTLS | `_paginate_offset` (`$skip`/`$top`, stops on 204) | `_setup_session` with cert, `_get_url` override for `post()` (`{endpoint}.{subresource}.{verb}` pattern)                   |
| DeansListResource       | API key per school   | `_paginate_page`                                  | `_prepare_request` (school_id injection), `_get_url` (beta endpoint `-data` suffix logic), custom Avro writing in subclass |

### Vestigial resources (preserved, not migrated)

AdpWorkforceManagerResource, MClassResource, DibelsDataSystemResource,
CouchdropResource, AlchemerResource — builder functions exist but are not called
by any code location. Left as-is.

## Testing

### Base class unit tests

`tests/libraries/http/test_resources.py` — mocked with `responses` or
`unittest.mock`, no real API calls.

- Session lifecycle: `setup_for_execution` assigns `_log`, calls
  `_setup_session`, teardown closes session
- URL construction: `_get_url` joins base + parts correctly
- Request pipeline: `_request` calls hooks in correct order
- Retry: tenacity retries on 429/5xx, respects `_get_retry_after` wait time,
  stops after max attempts
- 429 with Retry-After: default `_get_retry_after` parses `Retry-After`
  (seconds), `X-RateLimit-Reset` (epoch)
- 401 handling: calls `_reauthenticate`, retries
- Pagination: each of `_paginate_cursor`, `_paginate_offset`, `_paginate_page`
  tested with mocked callbacks — multi-page, single page, empty first page

### Subclass mocked tests

Per-resource tests verifying override behavior:

- `_setup_session` sets correct headers/auth
- `_get_url` produces correct URLs per resource's conventions
- Override-specific behavior: Zendesk `_get_retry_after` parsing, DeansList
  `_prepare_request` school_id injection, ADP WFN mTLS cert attachment

### Pagination contract tests

Per-resource tests with mocked multi-page response sequences using realistic
response shapes. Covers edge cases: single page, empty first page, partial last
page, malformed cursor.

### Integration validation

After each migration tier, run `dagster definitions validate` for every affected
code location.

### Existing integration tests

Existing `tests/resources/test_resource_*.py` files preserved as-is. These are
API exploration scripts requiring real credentials — not run in CI.

## Coding Standards

- Google-style docstrings per
  [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings),
  compatible with mkdocstrings
- `requires-python = ">=3.13"` — use built-in generics, `X | None`, etc.
- All public methods require return type annotations
- Use `pop` not `get` when extracting kwargs before spreading
- Lint suppression via `# trunk-ignore(<linter>/<rule>)` with reason comment
