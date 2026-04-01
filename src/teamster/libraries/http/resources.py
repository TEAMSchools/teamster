from dagster import ConfigurableResource, DagsterLogManager, InitResourceContext
from dagster_shared import check
from pydantic import PrivateAttr
from requests import Response, Session


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

    def _request(self, method: str, url: str, **kwargs) -> Response:
        """Dispatch an HTTP request through the session.

        Sets the default timeout, runs ``_prepare_request``, dispatches via
        ``_session.request``, logs the result at info level, and calls
        ``raise_for_status()``.

        Args:
            method: HTTP method string (e.g. ``"GET"``).
            url: Fully-qualified request URL.
            **kwargs: Additional keyword arguments forwarded to
                ``Session.request``.

        Returns:
            The :class:`requests.Response` object for a successful request.

        Raises:
            requests.HTTPError: If the response status indicates an error.
        """
        kwargs.setdefault("timeout", self.request_timeout)
        method, url, kwargs = self._prepare_request(method, url, kwargs)
        response = self._session.request(method=method, url=url, **kwargs)
        self._log.info(
            f"{method} {url} -> {response.status_code}"
            f" ({response.elapsed.total_seconds():.2f}s)"
        )
        response.raise_for_status()
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
