import logging
import select
import socket
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from cryptography.hazmat.primitives import hashes
from dagster_shared import check
from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko import RSAKey, SFTPAttributes, SFTPClient, SSHClient, Transport
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    IncompatiblePeer,
    NoValidConnectionsError,
    ProxyCommandFailure,
    SSHException,
)
from pydantic import Field
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential_jitter,
)

# Serializes mutation of `Transport._preferred_keys`, `Transport._key_info`,
# and `RSAKey.HASHES` across concurrent `enable_legacy_rsa` connects in the
# same process — without it, two threads can interleave save/restore and leak
# `ssh-rsa` past the legacy resource's call (Thread B captures A's mutated
# value as "original" and restores to it).
_PREFERRED_KEYS_LOCK = threading.Lock()

# Effectively "no rekey": larger than any single PowerSchool extract's byte
# volume, so paramiko's `need_rekey()` never trips on the tunnel (OpenSSH
# `RekeyLimit none`). Explicit `Transport.renegotiate_keys()` still works.
_REKEY_DISABLED_BYTES = 1 << 48

# `SSHClient.connect` hands `timeout` to `Transport.start_client()`, whose wait
# spans the banner read (`banner_timeout`, 15s) AND the key exchange that
# follows (`handshake_timeout`, 15s). dagster-ssh defaults `timeout` to 10s, so
# it expired first — and `start_client()` breaks out of its wait loop WITHOUT
# raising when its own deadline passes. `connect()` then fell through to
# `get_remote_server_key()`, which raises the misleading
# `SSHException("No existing session")` while the real negotiation kept running
# on an abandoned transport thread that logged an ERROR traceback seconds after
# the caller had given up (#4636).
#
# 45s clears paramiko's 30s negotiation ceiling with headroom. It does NOT need
# to cover `auth_timeout` (30s) — authentication runs after `start_client()`
# returns and enforces its own deadline.
# `tests/resources/test_resource_ssh_banner_timeout.py` reads the paramiko
# defaults live and fails if an upgrade ever pushes them past this.
_NEGOTIATION_TIMEOUT_SECONDS = 45

# Soft ceiling on the retry sequence: `stop_after_delay` is evaluated BETWEEN
# attempts, so an attempt starting just under the threshold still runs its full
# `_NEGOTIATION_TIMEOUT_SECONDS`, putting the true worst case nearer 165s. That
# is still well inside the 600s shortest SFTP sensor interval, whereas the
# unbounded five attempts plus backoff it replaces could reach ~4 minutes
# against a black-holed host.
_RETRY_DEADLINE_SECONDS = 120

# Deterministic `SSHException` subclasses: a config/compatibility mismatch that
# fails identically on every attempt, so retrying only burns backoff.
# `AuthenticationException` covers `BadAuthenticationType` and
# `PartialAuthentication`.
_NON_RETRYABLE_SSH_EXCEPTIONS = (
    AuthenticationException,
    BadHostKeyException,
    IncompatiblePeer,
    ProxyCommandFailure,
)

# paramiko reports its transient negotiation failures as a BARE `SSHException`
# ("Error reading SSH protocol banner", "No existing session", "Negotiation
# failed.") — there is no dedicated subclass to match on. The rest are NOT
# `SSHException` subclasses (`NoValidConnectionsError` is an `OSError`), so they
# have to be named separately.
#
# Public because SFTP sensors catch this same tuple to decide whether to skip a
# tick. `reraise=True` on `get_connection` re-raises the ORIGINAL exception once
# the retry budget is spent, so a sensor catching only `SSHException` would let
# a downed host (`NoValidConnectionsError`) or a reset peer
# (`ConnectionResetError`) fail the tick instead of skipping it. Keeping one
# tuple keeps the retry boundary and the skip boundary from drifting apart.
TRANSIENT_CONNECT_EXCEPTIONS = (
    SSHException,
    NoValidConnectionsError,
    TimeoutError,
    socket.gaierror,
    ConnectionResetError,
)


def _is_transient_connect_failure(exception: BaseException) -> bool:
    """Retry predicate for `get_connection`.

    Subtracting the deterministic subclasses from `SSHException` rather than
    dropping the base class outright: `c4541aa1b` did the latter, which
    correctly stopped retrying `IncompatiblePeer` / `BadHostKeyException` /
    `BadAuthenticationType` but also silently disabled the retry for every
    transient bare `SSHException` — including the banner read failure this retry
    exists for (#4636).
    """
    if isinstance(exception, _NON_RETRYABLE_SSH_EXCEPTIONS):
        return False

    return isinstance(exception, TRANSIENT_CONNECT_EXCEPTIONS)


class _DemoteTransportThreadErrors(logging.Filter):
    """Lower `paramiko.transport`'s ERROR records to WARNING.

    `Transport.run()` logs its exception message and full traceback at ERROR
    from a BACKGROUND thread, so GCP Error Reporting files a group even when the
    retry above recovers the connection on the next attempt. Two such groups
    (`CPuG15Xz8J-doAE`, `CO7X67XY7MG3YA`) were the two halves of one chained
    traceback, refiled every time an SFTP host was slow (#4636).

    No signal is lost: `run()` also stores the exception in `saved_exception`,
    which `start_client()` re-raises on the calling thread, so a failure the
    retry does NOT recover still propagates and gets logged at the run/tick
    level by Dagster. This is the vendored-library form of the rule in
    `core/CLAUDE.md` about not logging tracebacks inside retry-wrapped helpers.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            record.levelno = logging.WARNING
            record.levelname = logging.getLevelName(logging.WARNING)

        return True


def _demote_paramiko_transport_errors() -> None:
    """Install the demoting filter once per process.

    A logger-level filter only runs for records logged directly to that logger,
    which is exactly the target: `Transport._log` writes to `paramiko.transport`
    itself. Child loggers (`paramiko.transport.sftp`) are untouched.

    Called from `get_connection` rather than at import so that importing this
    module does not mutate global logging state in processes that never open an
    SSH connection. Installing here is still early enough: the transport thread
    that logs the traceback is not started until `connect()` runs below.
    """
    logger = logging.getLogger("paramiko.transport")

    if not any(isinstance(f, _DemoteTransportThreadErrors) for f in logger.filters):
        logger.addFilter(_DemoteTransportThreadErrors())


# `RSAKey` subclass that accepts `ssh-rsa` (SHA-1) signatures. paramiko 5.0
# keeps `ssh-rsa` out of `RSAKey.HASHES` (declared `Final`) to refuse SHA-1;
# placing this subclass in a transport instance's `_key_info["ssh-rsa"]`
# re-enables SHA-1 host-key verification at rekey WITHOUT mutating the
# process-global `RSAKey.HASHES` (which would weaken every RSA verification in
# the process). Built via `type()` because a static subclass cannot override
# the `Final` `HASHES` attribute.
_LegacyRSAKey = type(
    "_LegacyRSAKey",
    (RSAKey,),
    {"HASHES": {**RSAKey.HASHES, "ssh-rsa": hashes.SHA1}},
)


def _persist_legacy_rsa(transport: Transport) -> None:
    """Keep `ssh-rsa` usable for the LIFETIME of one transport, and disable
    paramiko's periodic rekey on it.

    `get_connection` re-enables ssh-rsa only for the initial handshake and
    reverts the class-level patch immediately. But paramiko renegotiates keys
    mid-stream every `Packetizer.REKEY_BYTES` (512 MiB); against an ssh-rsa-only
    server (GlobalSCAPE EFT, the PowerSchool host) that rekey's KEXINIT would no
    longer offer ssh-rsa, negotiation would fail, and the dropped transport
    surfaced as `oracledb DPY-4011` on the forwarded Oracle connection.

    All three assignments are scoped to the transport instance / a subclass, so
    (unlike the class-level patch in `get_connection`) they never leak ssh-rsa
    to other connections in the process. `getattr` reads the instance attribute
    before the class attribute, so a mid-stream rekey sees ssh-rsa again.
    """
    transport._preferred_keys = tuple(transport._preferred_keys) + ("ssh-rsa",)
    transport._key_info = {**transport._key_info, "ssh-rsa": _LegacyRSAKey}
    transport.packetizer.REKEY_BYTES = _REKEY_DISABLED_BYTES
    transport.packetizer.REKEY_PACKETS = _REKEY_DISABLED_BYTES


class SSHResource(DagsterSSHResource):
    tunnel_remote_host: str | None = None
    test: bool = False
    # paramiko 5.0 dropped `ssh-rsa` (SHA-1 RSA host keys) from its default
    # _preferred_keys. Set True to re-enable ssh-rsa for servers that only
    # advertise it (otherwise KEX negotiation fails with IncompatiblePeer).
    enable_legacy_rsa: bool = False
    # Overrides dagster-ssh's 10s default, which expired before paramiko
    # finished negotiating. See `_NEGOTIATION_TIMEOUT_SECONDS`.
    timeout: int = Field(
        default=_NEGOTIATION_TIMEOUT_SECONDS,
        description=(
            "Timeout for the attempt to connect to remote host. Must exceed"
            " paramiko's banner_timeout + handshake_timeout or connect() reports"
            " a misleading 'No existing session' and abandons the transport"
            " thread."
        ),
    )

    @retry(
        stop=stop_after_attempt(5) | stop_after_delay(_RETRY_DEADLINE_SECONDS),
        wait=wait_exponential_jitter(initial=2, max=30),
        # Retry true transients only — but by SUBTRACTING the deterministic
        # subclasses from SSHException rather than dropping the base class,
        # which would take the transient bare SSHExceptions with it.
        retry=retry_if_exception(_is_transient_connect_failure),
        reraise=True,
    )
    def get_connection(self) -> SSHClient:
        _demote_paramiko_transport_errors()

        if not self.enable_legacy_rsa:
            return super().get_connection()

        # Re-enable ssh-rsa at three layers paramiko 5.0 deliberately disabled:
        #   1. `Transport._preferred_keys` (used by `_filter_algorithm("keys")`
        #      at KEXINIT) — without it, negotiation fails with
        #      `IncompatiblePeer: no acceptable host key`.
        #   2. `Transport._key_info` (algorithm->PKey-class dict consulted by
        #      `_verify_key` on the server's host key) — without it, KEX
        #      succeeds and then raises `KeyError: 'ssh-rsa'`.
        #   3. `RSAKey.HASHES` (signature-algorithm->hash dict consulted by
        #      `verify_ssh_sig`) — paramiko intentionally keeps ssh-rsa out of
        #      HASHES to refuse SHA-1 signatures. Without it, the host-key
        #      parse succeeds and then `verify_ssh_sig` returns False, raising
        #      `Signature verification (ssh-rsa) failed.`
        # All three temporary mutations are held under the module-level lock
        # so concurrent connects can't see partial state or leak past restore.
        with _PREFERRED_KEYS_LOCK:
            original_preferred_keys: tuple[str, ...] = Transport._preferred_keys
            original_key_info: dict = Transport._key_info
            original_rsa_hashes: dict = RSAKey.HASHES
            Transport._preferred_keys = original_preferred_keys + ("ssh-rsa",)
            Transport._key_info = {**original_key_info, "ssh-rsa": RSAKey}
            RSAKey.HASHES = {**original_rsa_hashes, "ssh-rsa": hashes.SHA1}
            try:
                client = super().get_connection()
            finally:
                Transport._preferred_keys = original_preferred_keys
                Transport._key_info = original_key_info
                RSAKey.HASHES = original_rsa_hashes

        # The class-level patch above is reverted the instant the handshake
        # returns; persist ssh-rsa on THIS transport (and disable auto-rekey) so
        # a mid-stream 512 MiB rekey can't drop the connection. See
        # `_persist_legacy_rsa`.
        _persist_legacy_rsa(check.not_none(value=client.get_transport()))
        return client

    def listdir_attr_r(
        self,
        sftp_client: SFTPClient,
        remote_dir: str = ".",
        exclude_dirs: list[str] | None = None,
        min_mtime: float | None = None,
        dir_mtimes: dict[str, float] | None = None,
    ) -> list[tuple[SFTPAttributes, str]]:
        """Recursively list SFTP files with attributes.

        The ``dir_mtimes`` parameter enables subtree pruning: a directory whose
        ``st_mtime`` has not advanced since the cached value is skipped. This
        is only sound when the SFTP server advances parent-directory mtime on
        entry adds/removes/renames (POSIX semantics). Not all SFTP servers
        honor this — Amplify mClass returns stale directory mtimes, causing the
        prune to silently drop new files. Before opting a new sensor into
        ``dir_mtimes``, verify the server propagates by checking whether any
        directory's ``st_mtime`` is older than the max ``st_mtime`` of its
        descendants; if so, do not pass ``dir_mtimes``.
        """
        if exclude_dirs is None:
            exclude_dirs = []

        if remote_dir in exclude_dirs:
            return []

        files: list[tuple[SFTPAttributes, str]] = []
        for file in sftp_client.listdir_attr(remote_dir):
            path = str(Path(remote_dir) / file.filename)
            mtime = check.not_none(value=file.st_mtime)

            if S_ISDIR(check.not_none(value=file.st_mode)):
                if dir_mtimes is not None:
                    cached_mtime = dir_mtimes.get(path)
                    if cached_mtime is not None and mtime <= cached_mtime:
                        continue

                files.extend(
                    self.listdir_attr_r(
                        sftp_client=sftp_client,
                        remote_dir=path,
                        exclude_dirs=exclude_dirs,
                        min_mtime=min_mtime,
                        dir_mtimes=dir_mtimes,
                    )
                )

                if dir_mtimes is not None:
                    dir_mtimes[path] = mtime
            elif S_ISREG(check.not_none(value=file.st_mode)):
                if min_mtime is None or mtime > min_mtime:
                    files.append((file, path))

        return files

    @contextmanager
    def open_ssh_tunnel(
        self, local_port: int = 1521, remote_port: int = 1521
    ) -> Iterator[int]:
        """In-process SSH local port forward.

        Replaced the retired sshpass-subprocess tunnel (#4442): no password
        file mount, no readiness race, host-key verification kept
        (get_connection handles legacy ssh-rsa and transient-failure retry).
        Yields the bound local port; pass local_port=0 for an ephemeral port.
        """
        client = self.get_connection()
        server: _ForwardServer | None = None

        try:
            transport = check.not_none(value=client.get_transport())

            server = _ForwardServer(
                server_address=("127.0.0.1", local_port),
                RequestHandlerClass=_make_forward_handler(
                    transport=transport,
                    remote_host=check.not_none(value=self.tunnel_remote_host),
                    remote_port=remote_port,
                    log=self.log,
                ),
            )

            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            yield server.server_address[1]
        finally:
            # Stop accepting new connections, then close the SSH
            # client/transport BEFORE closing the listener. Closing the
            # transport EOFs every open `direct-tcpip` channel, which makes a
            # handler thread blocked in
            # `select.select([self.request, channel], [], [])` on a
            # still-open forwarded connection return and unwind on its own.
            # Only then is it safe to call `server_close()`. `server` stays
            # `None` if construction raised before assignment (e.g.
            # `tunnel_remote_host` unset) — guard both server calls so
            # `client.close()` (paramiko no-ops on a second call, so this is
            # the single close site regardless of path) still runs.
            if server is not None:
                server.shutdown()

            client.close()

            if server is not None:
                # `_ForwardServer.block_on_close = False` is a bounded
                # backstop on top of the ordering above: `server_close()`
                # never joins per-connection handler threads (the
                # `ThreadingMixIn.block_on_close=True` default would join
                # with no timeout), so a thread that is somehow still stuck
                # can't hang cleanup — it's already `daemon_threads = True`,
                # so it won't block interpreter exit either.
                server.server_close()


class _ForwardServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    # See the cleanup-ordering comment in `open_ssh_tunnel`: without
    # this, `server_close()` joins every per-connection handler thread with
    # no timeout, which can hang forever on a handler parked in `select()`.
    block_on_close = False


def _make_forward_handler(
    transport: Transport,
    remote_host: str,
    remote_port: int,
    log: logging.Logger,
) -> type[socketserver.BaseRequestHandler]:
    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            try:
                channel = transport.open_channel(
                    kind="direct-tcpip",
                    dest_addr=(remote_host, remote_port),
                    src_addr=self.request.getpeername(),
                )
            except Exception as e:
                log.warning(
                    f"direct-tcpip channel to {remote_host}:{remote_port} failed: {e}"
                )
                return

            if channel is None:
                log.warning("direct-tcpip channel rejected by server")
                return

            try:
                while True:
                    r, _, _ = select.select([self.request, channel], [], [])
                    if self.request in r:
                        data = self.request.recv(16384)
                        if len(data) == 0:
                            break
                        # `Channel.send()` may write fewer bytes than given
                        # (returns the count) — `sendall()` loops until the
                        # full buffer is written, preventing a short write
                        # from silently truncating the forwarded stream.
                        channel.sendall(data)
                    if channel in r:
                        data = channel.recv(16384)
                        if len(data) == 0:
                            break
                        # `socket.send()` has the same short-write behavior as
                        # `Channel.send()` above — use `sendall()` here too.
                        self.request.sendall(data)
            finally:
                channel.close()
                self.request.close()

    return Handler
