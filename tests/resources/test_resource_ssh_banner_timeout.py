"""Regression tests for the SFTP banner-timeout inversion and the lost
transient retry (#4636).

Two independent defects turned a slow SSH banner into a failed sensor tick plus
a pair of false-positive GCP Error Reporting groups:

1. **Timeout inversion.** `SSHResource.timeout` defaulted to 10s (dagster-ssh),
   but it is passed to `Transport.start_client()`, whose wait spans BOTH the
   banner read (`banner_timeout`, 15s) and the key exchange that follows
   (`handshake_timeout`, 15s) — a 30s budget. `start_client()` breaks out of its
   wait loop WITHOUT raising when its own deadline passes (`transport.py`, "if
   event.is_set() or ... >= max_time: break"), so `SSHClient.connect` fell
   through to `get_remote_server_key()`, which raises the misleading
   `SSHException("No existing session")` — while the real banner read continued
   on an orphaned transport thread that logged an ERROR traceback seconds after
   the caller had already given up.

2. **Lost transient retry.** `c4541aa1b` narrowed `get_connection`'s tenacity
   predicate to drop `SSHException`, correctly excluding the deterministic
   subclasses (`IncompatiblePeer` / `BadHostKeyException` /
   `BadAuthenticationType`) but also excluding every transient bare
   `SSHException` — including the banner read failure the retry existed for.

These tests need no external credentials: the loopback server accepts the TCP
connection and then stays silent, which is exactly what a slow SFTP host looks
like to paramiko.
"""

import importlib
import logging
import socket
import threading
from collections.abc import Callable
from zoneinfo import ZoneInfo

import pytest
from dagster import SkipReason, asset, build_sensor_context
from paramiko import RSAKey, SSHClient, Transport
from paramiko.ssh_exception import (
    AuthenticationException,
    BadAuthenticationType,
    BadHostKeyException,
    IncompatiblePeer,
    NoValidConnectionsError,
    SSHException,
)
from tenacity import stop_after_attempt, wait_none

from teamster.libraries.edplan.sensors import build_edplan_sftp_sensor
from teamster.libraries.ssh.resources import SSHResource


class _SilentBannerServer:
    """Accepts the TCP connection, then never sends an SSH banner.

    Mirrors a slow/overloaded SFTP host (`sftp.titank12.com` during the
    2026-07-30 incident): the socket connects fine, so this is NOT a
    `NoValidConnectionsError` / `ConnectionRefusedError` path — paramiko gets as
    far as waiting on the protocol banner and then stalls.
    """

    def __init__(self) -> None:
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(8)

        self._socks: list[socket.socket] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        return self._listener.getsockname()[1]

    def _serve(self) -> None:
        while True:
            try:
                sock, _ = self._listener.accept()
            except OSError:
                return  # listener closed → stop accepting
            # Hold the connection open and send nothing.
            self._socks.append(sock)

    def close(self) -> None:
        self._listener.close()
        for sock in self._socks:
            try:
                sock.close()
            except OSError:
                pass


@pytest.fixture
def silent_banner_server():
    server = _SilentBannerServer()
    try:
        yield server
    finally:
        server.close()


def _resource(port: int, **kwargs) -> SSHResource:
    resource = SSHResource(
        remote_host="127.0.0.1",
        remote_port=port,
        username="svc",
        password="pw",
        no_host_key_check=True,
        **kwargs,
    )
    # Wires the logger without running `setup_for_execution` (no secret file /
    # ~/.ssh/config read), matching tests/resources/test_resource_ssh_rekey.py.
    resource.set_logger(logging.getLogger("test_ssh_banner_timeout"))
    return resource


def _connect_once(resource: SSHResource) -> SSHClient:
    """Call `get_connection` with retry collapsed to a single attempt.

    The connect-path tests below run against paramiko's REAL banner timeout —
    scaling it down would also erase the inversion they exist to catch — so a
    full retry budget would multiply an already-slow test by five.
    """
    retry_with = SSHResource.get_connection.retry_with  # type: ignore[attr-defined]
    return retry_with(stop=stop_after_attempt(1))(resource)


def _connect_without_backoff(resource: SSHResource) -> SSHClient:
    """Call `get_connection` with the retry budget intact but no backoff.

    The predicate tests assert HOW MANY attempts happen, not how long tenacity
    sleeps between them; keeping the real `wait_exponential_jitter` would add
    ~30s per parametrized case.
    """
    retry_with = SSHResource.get_connection.retry_with  # type: ignore[attr-defined]
    return retry_with(wait=wait_none())(resource)


def test_default_timeout_outlasts_paramiko_negotiation():
    """`SSHResource.timeout` must outlast everything `start_client()` covers.

    `SSHClient.connect` passes `timeout` to `start_client()`, whose wait spans
    BOTH the banner read (`banner_timeout`) and the key exchange that follows
    (`handshake_timeout`) — so the budget has to clear their sum. `auth_timeout`
    is deliberately excluded: authentication happens after `start_client()`
    returns and raises on its own deadline.

    Under-budgeting here is not a slow failure, it is a WRONG one:
    `start_client()` breaks out of its wait loop without raising, and
    `connect()` falls through to `get_remote_server_key()` → "No existing
    session", leaving the real negotiation running on an abandoned thread.

    The paramiko defaults are read live rather than hardcoded so an upgrade that
    raises them fails this test instead of silently reintroducing the inversion.
    """
    negotiation_budget = _paramiko_negotiation_budget()

    timeout = SSHResource(remote_host="127.0.0.1", username="svc").timeout

    assert timeout > negotiation_budget, (
        f"SSHResource.timeout ({timeout}s) must exceed paramiko's banner_timeout"
        f" + handshake_timeout ({negotiation_budget}s), or start_client()"
        " abandons the transport thread and connect() reports 'No existing"
        " session'"
    )


@pytest.mark.parametrize(
    "module_name",
    [
        "teamster.core.resources",
        "teamster.code_locations.kipptaf.resources",
        "teamster.code_locations.kippmiami.resources",
    ],
)
def test_no_configured_ssh_resource_undercuts_the_negotiation_budget(module_name: str):
    """Every configured `SSHResource` must clear the same invariant.

    Raising the default is only half the guarantee — a per-resource `timeout=`
    override puts that one host back under the ceiling on its own. Three did:
    `SSH_EDPLAN`, `SSH_RESOURCE_CLEVER`, and `SSH_RESOURCE_ILLUMINATE` all set
    `timeout=30`, which sits exactly ON paramiko's 30s budget rather than above
    it — so they would have kept failing with "No existing session" even after
    the default moved.
    """
    module = importlib.import_module(module_name)

    negotiation_budget = _paramiko_negotiation_budget()

    ssh_resources = {
        name: value
        for name, value in vars(module).items()
        if isinstance(value, SSHResource)
    }

    assert ssh_resources, f"expected SSHResource singletons in {module_name}"

    undercutting = {
        name: resource.timeout
        for name, resource in ssh_resources.items()
        if resource.timeout <= negotiation_budget
    }

    assert not undercutting, (
        "these SSH resources set a timeout at or below paramiko's"
        f" {negotiation_budget}s negotiation budget: {undercutting}"
    )


def test_silent_banner_raises_banner_error_not_no_existing_session(
    silent_banner_server,
):
    """A stalled banner must surface as the real banner-read failure.

    Before the fix this raised `SSHException("No existing session")` — a
    misleading message that made the incident look like an auth/session problem
    rather than a slow host.
    """
    resource = _resource(silent_banner_server.port)

    with pytest.raises(SSHException) as exc_info:
        _connect_once(resource)

    message = str(exc_info.value)

    assert "No existing session" not in message, (
        "connect() fell through start_client() without raising — the timeout"
        f" inversion is back (got: {message!r})"
    )
    assert "banner" in message.lower(), (
        f"expected the protocol-banner read failure, got: {message!r}"
    )


def test_silent_banner_leaves_no_orphaned_transport_thread(
    silent_banner_server,
):
    """The failed connect must not leave a paramiko transport thread running.

    An orphaned thread keeps reading the dead socket and then logs its own ERROR
    traceback after the caller has moved on — the source of both Error Reporting
    groups in #4636, and a socket/thread leak multiplied by every retry attempt.
    """
    resource = _resource(silent_banner_server.port)

    # `Transport` subclasses `threading.Thread` but never sets a name, so match
    # on type rather than `thread.name` (which is a default "Thread-N").
    before = {id(t) for t in threading.enumerate() if isinstance(t, Transport)}

    with pytest.raises(SSHException):
        _connect_once(resource)

    started = [
        t
        for t in threading.enumerate()
        if isinstance(t, Transport) and id(t) not in before
    ]

    # Allow a short unwind after the exception propagates — but stay well under
    # the banner timeout, so a thread abandoned mid-read is still running here.
    for thread in started:
        thread.join(timeout=2)

    orphaned = [t for t in started if t.is_alive()]

    assert not orphaned, (
        f"{len(orphaned)} paramiko transport thread(s) still running after a"
        " failed connect — connect() returned while the transport was still"
        " negotiating"
    )


def _count_attempts(monkeypatch, exception: BaseException) -> int:
    """Drive `get_connection` against an always-failing connect, return the
    number of attempts tenacity made."""
    attempts = 0

    def _always_fail(_self) -> SSHClient:
        nonlocal attempts
        attempts += 1
        raise exception

    monkeypatch.setattr(
        "teamster.libraries.ssh.resources.DagsterSSHResource.get_connection",
        _always_fail,
    )

    resource = _resource(port=22)

    with pytest.raises(type(exception)):
        _connect_without_backoff(resource)

    return attempts


def _paramiko_negotiation_budget() -> float:
    """Everything `Transport.start_client()`'s wait has to outlast.

    Read from a live `Transport` rather than hardcoded, so a paramiko upgrade
    that raises either default fails the callers instead of silently
    reintroducing the inversion.
    """
    sock_a, sock_b = socket.socketpair()
    try:
        transport = Transport(sock=sock_a)
        try:
            return transport.banner_timeout + transport.handshake_timeout
        finally:
            transport.close()
    finally:
        sock_a.close()
        sock_b.close()


def _bad_host_key() -> BadHostKeyException:
    # `BadHostKeyException.__init__` calls `get_base64()` on both keys, so they
    # have to be real. 1024 bits keeps generation cheap — this key only ever
    # gets formatted into an error message.
    key = RSAKey.generate(1024)
    return BadHostKeyException("host", key, key)


@pytest.mark.parametrize(
    "build_exception",
    [
        lambda: SSHException("Error reading SSH protocol banner"),
        lambda: SSHException("No existing session"),
        lambda: SSHException("Negotiation failed."),
        lambda: TimeoutError(),
        lambda: ConnectionResetError(),
        lambda: socket.gaierror(),
    ],
    ids=[
        "banner-read",
        "no-existing-session",
        "negotiation-failed",
        "timeout",
        "connection-reset",
        "dns",
    ],
)
def test_transient_failures_are_retried(
    monkeypatch, build_exception: Callable[[], BaseException]
):
    """Transient failures must exhaust the retry budget before giving up.

    `SSHException` is the base class of paramiko's transient negotiation errors.
    Dropping it from the predicate (`c4541aa1b`) silently disabled the retry for
    the single most common SFTP failure mode — the banner read.
    """
    exception = build_exception()
    attempts = _count_attempts(monkeypatch, exception)

    assert attempts == 5, (
        f"expected 5 attempts for transient {type(exception).__name__}"
        f" ({str(exception)!r}), got {attempts}"
    )


@pytest.mark.parametrize(
    "build_exception",
    [
        lambda: IncompatiblePeer("no acceptable host key"),
        lambda: BadAuthenticationType("bad type", ["publickey"]),
        _bad_host_key,
        lambda: AuthenticationException("auth failed"),
    ],
    ids=["incompatible-peer", "bad-auth-type", "bad-host-key", "auth-failed"],
)
def test_deterministic_failures_are_not_retried(
    monkeypatch, build_exception: Callable[[], BaseException]
):
    """Deterministic config failures must fail fast on the first attempt.

    These are all `SSHException` SUBCLASSES, so widening the predicate back to
    the bare base class would burn ~30s of backoff per call re-failing
    identically. That regression is what `c4541aa1b` set out to fix, and this
    test keeps the fix for #4636 from undoing it.
    """
    exception = build_exception()
    attempts = _count_attempts(monkeypatch, exception)

    assert attempts == 1, (
        f"deterministic {type(exception).__name__} must not be retried, got"
        f" {attempts} attempts"
    )


@pytest.mark.parametrize(
    "build_exception",
    [
        lambda: SSHException("Error reading SSH protocol banner"),
        lambda: NoValidConnectionsError({("10.0.0.1", 22): ConnectionRefusedError()}),
        lambda: TimeoutError("timed out"),
        lambda: ConnectionResetError("reset by peer"),
        lambda: socket.gaierror("name resolution failed"),
    ],
    ids=["banner-read", "host-down", "timeout", "connection-reset", "dns"],
)
def test_sftp_sensor_skips_rather_than_fails_on_any_transient_failure(
    monkeypatch, build_exception: Callable[[], BaseException]
):
    """A sensor must skip the tick for everything `get_connection` retries.

    `reraise=True` means an exhausted retry budget re-raises the ORIGINAL
    exception, and four of the five transient types are NOT `SSHException`
    subclasses. A sensor catching only `SSHException` therefore still failed the
    tick when a host was simply down (`NoValidConnectionsError`) or reset the
    connection (`ConnectionResetError`) — the exact case `c4541aa1b` added to
    the retry set because it had been seen in production.

    Driving the real sensor is what makes this meaningful: asserting the tuple's
    contents would just restate the constant.
    """
    result = _evaluate_edplan_sensor(monkeypatch, build_exception())

    assert isinstance(result, SkipReason), (
        "a transient failure escaped the sensor and failed the tick; it should"
        " have produced a SkipReason"
    )


@pytest.mark.parametrize(
    "build_exception",
    [
        lambda: AuthenticationException("auth failed"),
        lambda: BadAuthenticationType("bad type", ["publickey"]),
        _bad_host_key,
        lambda: IncompatiblePeer("no acceptable host key"),
    ],
    ids=["auth-failed", "bad-auth-type", "bad-host-key", "incompatible-peer"],
)
def test_sftp_sensor_fails_the_tick_on_deterministic_failures(
    monkeypatch, build_exception: Callable[[], BaseException]
):
    """A deterministic failure must FAIL the tick, not skip it.

    A rotated credential or a changed host key fails identically forever.
    Skipping renders that indistinguishable from "no new files" in the Dagster
    UI, so ingestion would stop silently and indefinitely — a worse outcome than
    a noisy tick failure, because nothing surfaces at all.

    These are all `SSHException` subclasses, so a blanket
    `except SSHException` / `except TRANSIENT_CONNECT_EXCEPTIONS` swallows every
    one of them.
    """
    exception = build_exception()

    with pytest.raises(type(exception)):
        _evaluate_edplan_sensor(monkeypatch, exception)


def _evaluate_edplan_sensor(monkeypatch, exception: BaseException):
    """Run a real edplan sensor whose every connect attempt raises `exception`."""

    def _always_fail(_self) -> SSHClient:
        raise exception

    # Patch the decorated method itself, so the retry budget is bypassed and the
    # test exercises the sensor's skip boundary rather than tenacity.
    monkeypatch.setattr(SSHResource, "get_connection", _always_fail)

    @asset(name="edplan_probe", metadata={"remote_file_regex": r"(?P<date>.+)\.csv"})
    def _edplan_probe() -> None: ...

    sensor_def = build_edplan_sftp_sensor(
        asset=_edplan_probe,
        code_location="test",
        execution_timezone=ZoneInfo("America/New_York"),
    )

    context = build_sensor_context(
        resources={"ssh_edplan": SSHResource(remote_host="127.0.0.1", username="svc")}
    )

    return sensor_def(context)


def test_transport_thread_errors_do_not_reach_error_severity(caplog):
    """paramiko's transport thread must not log at ERROR.

    `Transport.run()` logs its exception traceback at ERROR from a BACKGROUND
    thread, so GCP Error Reporting files a group even when the retry above
    recovers the connection. Unrecovered failures still surface as a raised
    exception that Dagster logs at the run/tick level, so demoting this
    particular logger loses no signal.

    Same trap `core/CLAUDE.md` already documents for `log.exception` inside
    retry-wrapped helpers — here it comes from a vendored logger.
    """
    logger = logging.getLogger("paramiko.transport")

    with caplog.at_level(logging.DEBUG, logger="paramiko.transport"):
        logger.error("Exception (client): Error reading SSH protocol banner")
        logger.error("Traceback (most recent call last):\n  ...")

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]

    assert not error_records, (
        "paramiko.transport still emits ERROR-severity records; GCP Error"
        " Reporting will keep filing false-positive groups for transient"
        f" failures the retry recovers ({[r.getMessage() for r in error_records]})"
    )
