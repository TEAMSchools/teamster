import types

import pytest
from dagster import EnvVar, build_init_resource_context, build_resources
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout
from tableauserverclient.server.endpoint.exceptions import (
    FailedSignInError,
    InternalServerError,
)
from tenacity import wait_none

from teamster.libraries.tableau.resources import TableauServerResource


def get_tableau_resource():
    with build_resources(
        resources={
            "tableau": TableauServerResource(
                server_address=EnvVar("TABLEAU_SERVER_ADDRESS"),
                site_id=EnvVar("TABLEAU_SITE_ID"),
                token_name=EnvVar("TABLEAU_TOKEN_NAME"),
                personal_access_token=EnvVar("TABLEAU_PERSONAL_ACCESS_TOKEN"),
            )
        }
    ) as resources:
        tableau: TableauServerResource = resources.tableau

    tableau.setup_for_execution(context=build_init_resource_context())

    return tableau


def test_tableau_workbook_refresh():
    tableau = get_tableau_resource()

    workbook = tableau._server.workbooks.get_by_id(
        "7adabf6e-fa59-4d60-bca8-de3a67005a53"
    )

    tableau._server.workbooks.refresh(workbook)


def test_tableau_get_user():
    from tableauserverclient import Pager

    tableau = get_tableau_resource()

    # print the names of the groups on the server
    for group in Pager(endpoint=tableau._server.users):
        print(group.name, group.id)


def test_tableau_add_group_users():
    from tableauserverclient import Pager

    tableau = get_tableau_resource()

    group_item = [
        group
        for group in Pager(endpoint=tableau._server.groups)
        if group.name == "Teacher Gradebook Email - Auto - Newark"
    ][0]

    users = [
        user
        for user in Pager(endpoint=tableau._server.users)
        if user.email
        in ["cbini@kippteamandfamily.org", "grangel@kippteamandfamily.org"]
    ]

    tableau._server.groups.add_users(group_item=group_item, users=users)


def _build_offline_resource(sign_in_fn) -> TableauServerResource:
    """Instantiate the resource with a fake server, bypassing the network path."""
    tableau = TableauServerResource(
        server_address="https://tableau.example.com",
        token_name="x",
        personal_access_token="x",
        site_id="x",
    )

    object.__setattr__(
        tableau,
        "_server",
        types.SimpleNamespace(auth=types.SimpleNamespace(sign_in=sign_in_fn)),
    )

    return tableau


def _internal_server_error(status_code: int) -> InternalServerError:
    """Build a TSC ``InternalServerError`` as ``sign_in`` raises it on a 5xx."""
    return InternalServerError(
        types.SimpleNamespace(status_code=status_code, content=b"gateway error"),
        "https://tableau.example.com/auth/signin",
    )


def test_sign_in_retries_on_network_faults(monkeypatch: pytest.MonkeyPatch):
    """A connection reset or timeout during PAT sign-in is transient and retried.

    Regression for prod run 136d2259: the Tableau Server dropped the TCP
    connection mid-TLS-handshake during ``auth.sign_in``, surfacing as a
    ``requests.exceptions.ConnectionError``. The unprotected init path failed the
    resource, the step, and (after the run-level auto-retry hit the same window)
    the whole run. A bounded backoff must recover a single blip instead.
    """
    # make tenacity backoff instant for the test
    monkeypatch.setattr(TableauServerResource._sign_in.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def sign_in_fn(_auth) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RequestsConnectionError("Connection reset by peer")
        if calls["n"] == 2:
            raise Timeout("read timed out")

    tableau = _build_offline_resource(sign_in_fn)

    tableau._sign_in()

    assert calls["n"] == 3


def test_sign_in_retries_on_internal_server_error(monkeypatch: pytest.MonkeyPatch):
    """A transient 5xx during sign-in is retried.

    ``tableauserverclient`` wraps a 5xx response in ``InternalServerError`` (not
    ``requests.HTTPError``). A gateway blip -- e.g. the server briefly having no
    healthy backend during a top-of-hour deploy -- is transient like a connection
    reset, so a bounded backoff must recover it rather than fail the run.
    """
    monkeypatch.setattr(TableauServerResource._sign_in.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def sign_in_fn(_auth) -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _internal_server_error(503)

    tableau = _build_offline_resource(sign_in_fn)

    tableau._sign_in()

    assert calls["n"] == 3


def test_sign_in_exhausts_on_persistent_connection_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """A persistent connection error is retried to the cap, then re-raised.

    A fault that never clears must still surface the original
    ``ConnectionError`` and fail the run rather than retry unbounded.
    """
    monkeypatch.setattr(TableauServerResource._sign_in.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def sign_in_fn(_auth) -> None:
        calls["n"] += 1
        raise RequestsConnectionError("Connection reset by peer")

    tableau = _build_offline_resource(sign_in_fn)

    with pytest.raises(RequestsConnectionError):
        tableau._sign_in()

    assert calls["n"] == 5


def test_sign_in_does_not_retry_on_auth_error(monkeypatch: pytest.MonkeyPatch):
    """A deterministic sign-in failure (an invalid or expired PAT) fails fast.

    ``tableauserverclient`` raises ``FailedSignInError`` on a 401. It is outside
    the retry predicate, so retrying it would only waste time and never recover.
    """
    monkeypatch.setattr(TableauServerResource._sign_in.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def sign_in_fn(_auth) -> None:
        calls["n"] += 1
        raise FailedSignInError(
            "401001", "Signin Error", "Invalid or expired token", "url"
        )

    tableau = _build_offline_resource(sign_in_fn)

    with pytest.raises(FailedSignInError):
        tableau._sign_in()

    assert calls["n"] == 1


def test_setup_for_execution_invokes_sign_in(monkeypatch: pytest.MonkeyPatch):
    """``setup_for_execution`` must call ``_sign_in`` (and pin the API version).

    The retry tests call ``_sign_in`` directly, so a regression that drops the
    ``self._sign_in()`` call in ``setup_for_execution`` would pass all of them.
    This closes that gap without a live connection.
    """
    calls = {"n": 0}

    def fake_sign_in(self) -> None:
        calls["n"] += 1

    monkeypatch.setattr(TableauServerResource, "_sign_in", fake_sign_in)

    tableau = TableauServerResource(
        server_address="https://tableau.example.com",
        token_name="x",
        personal_access_token="x",
        site_id="x",
    )

    tableau.setup_for_execution(context=build_init_resource_context())

    assert calls["n"] == 1
    assert tableau._server.version == "3.25"
