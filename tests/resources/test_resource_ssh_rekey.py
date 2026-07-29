"""Regression tests for the legacy-ssh-rsa mid-stream rekey failure (DPY-4011).

paramiko renegotiates session keys every 512 MiB (`Packetizer.REKEY_BYTES`).
`SSHResource.get_connection` re-enables the legacy `ssh-rsa` host-key algorithm
only for the initial handshake and reverts the (class-level) patch in a
`finally` the instant the handshake returns. Against an ssh-rsa-only server
(GlobalSCAPE EFT, the PowerSchool host) that left the returned connection unable
to renegotiate: the bulk dlt extract crossed 512 MiB mid-table, paramiko fired a
rekey whose KEXINIT no longer offered ssh-rsa, the server closed the transport,
and oracledb surfaced `DPY-4011: the database or network closed the connection`.

These tests spin up an in-process ssh-rsa-only server on loopback (no external
credentials needed) and assert `get_connection` returns a connection that can
survive a rekey. All ssh-rsa enabling in the harness is scoped to the server
Transport / host-key INSTANCES — never the shared `Transport` / `RSAKey` class
attributes — so the harness cannot mask a client-side regression by leaving a
global patch applied.
"""

import logging
import socket
import threading

import pytest
from cryptography.hazmat.primitives import hashes
from paramiko import RSAKey, ServerInterface, Transport
from paramiko.common import AUTH_SUCCESSFUL

from teamster.libraries.ssh.resources import SSHResource


class _PasswordServer(ServerInterface):
    def check_auth_password(self, username, password) -> int:
        return AUTH_SUCCESSFUL

    def get_allowed_auths(self, username) -> str:
        return "password"


class _RsaOnlyLoopbackServer:
    """In-process SSH server that advertises ONLY the legacy `ssh-rsa` host-key
    algorithm, mirroring the real PowerSchool GlobalSCAPE host."""

    def __init__(self) -> None:
        self._host_key = RSAKey.generate(2048)
        # Instance-scoped SHA-1 so this key can SIGN with ssh-rsa. paramiko 5.0
        # keeps ssh-rsa out of the class-level `RSAKey.HASHES` on purpose;
        # shadowing it on the instance keeps the mutation off the shared class.
        self._host_key.HASHES = {**RSAKey.HASHES, "ssh-rsa": hashes.SHA1}

        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)

        self._transports: list[Transport] = []
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
            self._socks.append(sock)
            transport = Transport(sock)
            transport.add_server_key(self._host_key)
            # INSTANCE-scoped (not the `Transport` class): offer ssh-rsa ONLY.
            transport._preferred_keys = ("ssh-rsa",)
            transport.server_key_dict = {"ssh-rsa": self._host_key}
            self._transports.append(transport)
            try:
                transport.start_server(server=_PasswordServer())
            except Exception:
                continue

    def close(self) -> None:
        self._listener.close()
        for transport in self._transports:
            transport.close()
        for sock in self._socks:
            try:
                sock.close()
            except OSError:
                pass


@pytest.fixture
def rsa_only_server():
    server = _RsaOnlyLoopbackServer()
    try:
        yield server
    finally:
        server.close()


def _legacy_rsa_resource(port: int) -> SSHResource:
    resource = SSHResource(
        remote_host="127.0.0.1",
        remote_port=port,
        username="svc",
        password="pw",
        test=True,
        enable_legacy_rsa=True,
        no_host_key_check=True,
    )
    # `get_connection` logs a warning under `no_host_key_check`; `set_logger`
    # wires the logger without running `setup_for_execution` (no secret file /
    # ~/.ssh/config read). PrivateAttr defaults (`_host_proxy`/`_key_obj`) stay
    # None → a direct loopback connect with password auth.
    resource.set_logger(logging.getLogger("test_ssh_rekey"))
    return resource


def test_legacy_rsa_connection_survives_rekey(rsa_only_server):
    """The returned connection must survive the rekey paramiko fires at 512 MiB.

    Reproduces DPY-4011: without persisting ssh-rsa past the initial handshake,
    `renegotiate_keys()` (the same KEXINIT paramiko sends automatically once
    `Packetizer.REKEY_BYTES` bytes have flowed) fails to negotiate a host-key
    algorithm with the ssh-rsa-only server and the transport dies.
    """
    resource = _legacy_rsa_resource(rsa_only_server.port)
    client = resource.get_connection()
    try:
        transport = client.get_transport()
        assert transport is not None and transport.is_active()

        # Force the exact renegotiation paramiko triggers mid-stream at 512 MiB.
        transport.renegotiate_keys()

        assert transport.is_active()
    finally:
        client.close()


def test_legacy_rsa_connection_disables_auto_rekey(rsa_only_server):
    """A legacy connection should not auto-rekey at all (OpenSSH `RekeyLimit
    none`), so the 512 MiB threshold that killed the extract is never reached.

    Explicit `renegotiate_keys()` still works — covered by the test above.
    """
    resource = _legacy_rsa_resource(rsa_only_server.port)
    client = resource.get_connection()
    try:
        transport = client.get_transport()
        assert transport is not None
        # Far above any single PowerSchool extract's byte volume.
        assert transport.packetizer.REKEY_BYTES >= (1 << 40)
    finally:
        client.close()
