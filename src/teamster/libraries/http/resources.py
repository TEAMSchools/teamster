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


class _NonRetryableHTTPError(Exception):
    """Wraps an HTTPError to prevent tenacity from retrying."""

    def __init__(self, cause: HTTPError) -> None:
        super().__init__(str(cause))
        self.cause = cause


class BaseHTTPResource(ConfigurableResource):
    """Base class for HTTP API resources built on requests.Session.

    Provides session lifecycle management, a composable request pipeline,
    URL construction, and HTTP verb convenience methods. Subclasses override
    ``_setup_session()`` to configure auth headers, base URL, and adapters.

    Attributes:
        request_timeout: Default timeout in seconds for all requests.
    """

    request_timeout: float = 60.0

    _session: Session = PrivateAttr(default_factory=Session)
    _base_url: str = PrivateAttr(default="")
    _log: DagsterLogManager = PrivateAttr()
    _reauth_attempted: bool = PrivateAttr(default=False)

    def setup_for_execution(self, context: InitResourceContext) -> None:
        """Assign the Dagster log manager and initialise the HTTP session.

        Args:
            context: Dagster resource initialisation context.
        """
        self._log = check.not_none(value=context.log)
        self._setup_session()

    def teardown_after_execution(self, context: InitResourceContext) -> None:
        """Close the HTTP session to release connections.

        Args:
            context: Dagster resource teardown context.
        """
        self._session.close()

    def _setup_session(self) -> None:
        """Initialise session state (auth, headers, base URL).

        Called by ``setup_for_execution``. Override in subclasses to configure
        the session before the first request is made. Default is a no-op.
        """

    def _prepare_request(
        self, method: str, url: str, kwargs: dict
    ) -> tuple[str, str, dict]:
        """Pre-request hook for modifying method, URL, or kwargs.

        Override to inject params, headers, or transform the request before it
        is dispatched. Default returns all arguments unchanged.

        Args:
            method: HTTP method string (e.g. ``"GET"``).
            url: Fully-qualified request URL.
            kwargs: Keyword arguments to pass to ``Session.request``.

        Returns:
            A ``(method, url, kwargs)`` tuple forwarded to ``_session.request``.
        """
        return method, url, kwargs

    def _get_retry_after(self, response: Response) -> float | None:
        """Parse the rate-limit wait time from response headers.

        Checks ``Retry-After`` (as seconds or HTTP-date) then
        ``X-RateLimit-Reset`` (as a Unix epoch timestamp).

        Args:
            response: The HTTP response to inspect.

        Returns:
            Seconds to wait as a float, or ``None`` if no relevant header
            is present.
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                try:
                    reset_dt = parsedate_to_datetime(retry_after)
                    delta = (reset_dt - datetime.now(tz=timezone.utc)).total_seconds()
                    return max(delta, 0.0)
                except Exception:
                    pass

        x_reset = response.headers.get("X-RateLimit-Reset")
        if x_reset is not None:
            try:
                return max(float(x_reset) - time.time(), 0.0)
            except ValueError:
                pass

        return None

    def _reauthenticate(self) -> None:
        """Refresh authentication credentials.

        Called once on a 401 response before retrying. Default re-raises the
        current exception. Subclasses override with token refresh logic.

        Raises:
            requests.HTTPError: Re-raises the triggering error by default.
        """
        raise

    def _handle_error(self, response: Response, error: HTTPError) -> None:
        """React to an HTTP error and decide whether to retry.

        Args:
            response: The HTTP response that triggered the error.
            error: The ``HTTPError`` raised by ``raise_for_status()``.

        Raises:
            requests.HTTPError: Always — either to let tenacity retry or to
                propagate a non-retryable failure.
        """
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
            self._log.error(f"Re-authentication failed: {error}")
            raise _NonRetryableHTTPError(error)

        if status >= 500:
            self._log.error(f"Server error {status}: {error}")
            raise error

        # Other 4xx — non-retryable
        self._log.error(f"Client error {status}: {error}")
        raise _NonRetryableHTTPError(error)

    def _request(self, method: str, url: str, **kwargs) -> Response:
        """Dispatch an HTTP request through the session with retry support.

        Resets the re-auth guard and delegates to ``_request_with_retry``.

        Args:
            method: HTTP method string (e.g. ``"GET"``).
            url: Fully-qualified request URL.
            **kwargs: Additional keyword arguments forwarded to
                ``Session.request``.

        Returns:
            The :class:`requests.Response` object for a successful request.

        Raises:
            requests.HTTPError: If the response status indicates a
                non-retryable error or retries are exhausted.
        """
        self._reauth_attempted = False
        try:
            return self._request_with_retry(method, url, **kwargs)
        except _NonRetryableHTTPError as exc:
            raise exc.cause from None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=60),
        retry=retry_if_exception_type(HTTPError),
        reraise=True,
    )
    def _request_with_retry(self, method: str, url: str, **kwargs) -> Response:
        """Inner retry loop for dispatching a single HTTP attempt.

        Decorated with tenacity retry logic (up to 3 attempts, exponential
        backoff with jitter, retries on ``HTTPError``).

        Args:
            method: HTTP method string (e.g. ``"GET"``).
            url: Fully-qualified request URL.
            **kwargs: Additional keyword arguments forwarded to
                ``Session.request``.

        Returns:
            The :class:`requests.Response` object for a successful request.

        Raises:
            requests.HTTPError: Propagated after retries are exhausted or for
                non-retryable status codes.
        """
        kwargs.setdefault("timeout", self.request_timeout)
        method, url, kwargs = self._prepare_request(method, url, kwargs)
        response = self._session.request(method=method, url=url, **kwargs)
        self._log.info(
            f"{method} {url} -> {response.status_code}"
            f" ({response.elapsed.total_seconds():.2f}s)"
        )
        try:
            response.raise_for_status()
        except HTTPError as exc:
            self._handle_error(response, exc)
        return response

    def _get_url(self, *parts: str) -> str:
        """Construct a URL by joining ``_base_url`` with path segments.

        Args:
            *parts: Path segments to append to ``_base_url``.

        Returns:
            The joined URL string. Returns ``_base_url`` when no parts are
            provided.
        """
        if not parts:
            return self._base_url
        return self._base_url + "/" + "/".join(parts)

    def get(self, *parts: str, **kwargs) -> Response:
        """Send a GET request.

        Args:
            *parts: Path segments forwarded to ``_get_url``.
            **kwargs: Additional keyword arguments forwarded to ``_request``.

        Returns:
            The :class:`requests.Response` object.
        """
        return self._request("GET", self._get_url(*parts), **kwargs)

    def post(self, *parts: str, **kwargs) -> Response:
        """Send a POST request.

        Args:
            *parts: Path segments forwarded to ``_get_url``.
            **kwargs: Additional keyword arguments forwarded to ``_request``.

        Returns:
            The :class:`requests.Response` object.
        """
        return self._request("POST", self._get_url(*parts), **kwargs)

    def put(self, *parts: str, **kwargs) -> Response:
        """Send a PUT request.

        Args:
            *parts: Path segments forwarded to ``_get_url``.
            **kwargs: Additional keyword arguments forwarded to ``_request``.

        Returns:
            The :class:`requests.Response` object.
        """
        return self._request("PUT", self._get_url(*parts), **kwargs)

    def delete(self, *parts: str, **kwargs) -> Response:
        """Send a DELETE request.

        Args:
            *parts: Path segments forwarded to ``_get_url``.
            **kwargs: Additional keyword arguments forwarded to ``_request``.

        Returns:
            The :class:`requests.Response` object.
        """
        return self._request("DELETE", self._get_url(*parts), **kwargs)
