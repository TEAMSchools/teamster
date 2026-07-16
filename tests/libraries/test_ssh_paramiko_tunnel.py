import logging
import os
import socket
import threading
import time
from unittest.mock import MagicMock


def _make_resource():
    from teamster.libraries.ssh.resources import SSHResource

    ssh_resource = SSHResource(
        remote_host="ssh.example.com",
        username="user",
        password="pw",  # fixture; gitleaks doesn't flag it (verified via trunk check)
        tunnel_remote_host="oracle.internal",
    )
    # Outside a real Dagster run, `_logger` (backing the `log` property used by
    # `open_ssh_tunnel_paramiko`) is only set via `setup_for_execution` or this
    # public setter — without it, `self.log` raises `CheckError`.
    ssh_resource.set_logger(logging.getLogger(__name__))
    return ssh_resource


def test_paramiko_tunnel_forwards_to_remote_bind():
    ssh_resource = _make_resource()

    # `select.select()` requires a real, pollable file descriptor for each
    # waited-on object — a bare MagicMock's `fileno()` isn't one. Back the
    # mocked channel with a pipe's read end. `channel.send`'s side effect
    # writes to the pipe, so the channel only becomes select()-ready *after*
    # the handler has forwarded the client's byte — deterministic, no sleep.
    read_fd, write_fd = os.pipe()

    try:
        channel = MagicMock()
        channel.fileno.return_value = read_fd
        channel.recv.return_value = b""  # remote closes once selected
        channel.send.side_effect = lambda data: os.write(write_fd, b".")

        transport = MagicMock()
        transport.open_channel.return_value = channel

        client = MagicMock()
        client.get_transport.return_value = transport

        # SSHResource is a frozen Pydantic (dagster ConfigurableResource)
        # model — regular `setattr`/`patch.object` on the instance raises
        # `ValidationError: frozen_instance`. `object.__setattr__` bypasses
        # Pydantic's overridden `__setattr__` and writes the instance
        # `__dict__` directly, which normal attribute lookup finds ahead of
        # the class method (see tests/resources/test_resource_adp_workforce_now.py).
        object.__setattr__(ssh_resource, "get_connection", lambda: client)

        with ssh_resource.open_ssh_tunnel_paramiko(local_port=0) as local_port:
            assert isinstance(local_port, int) and local_port > 0

            with socket.create_connection(("127.0.0.1", local_port), timeout=5) as s:
                # drive one byte through so the handler opens the channel
                s.sendall(b"x")
                s.recv(1)  # returns b"" when the handler closes
    finally:
        os.close(read_fd)
        os.close(write_fd)

    _, kwargs = transport.open_channel.call_args
    assert kwargs["dest_addr"] == ("oracle.internal", 1521)
    client.close.assert_called_once()


def test_paramiko_tunnel_listener_closes_on_exit():
    ssh_resource = _make_resource()

    client = MagicMock()
    client.get_transport.return_value = MagicMock()

    object.__setattr__(ssh_resource, "get_connection", lambda: client)

    with ssh_resource.open_ssh_tunnel_paramiko(local_port=0) as local_port:
        pass

    try:
        socket.create_connection(("127.0.0.1", local_port), timeout=1)
        connected = True
    except OSError:
        connected = False

    assert not connected


def test_paramiko_tunnel_cleanup_does_not_hang_on_stuck_handler():
    """Cleanup must not deadlock when a handler thread is mid-`select()`.

    Drives a forwarded connection that is still open (client socket not
    closed) when the `with` block exits, so its handler thread is genuinely
    parked in ``select.select([self.request, channel], [], [])`` — neither
    side is ever readable, since the pipe backing ``channel.fileno()`` is
    never written to and the client socket is deliberately left open.

    This is a regression guard, not a literal repro against the pre-fix
    commit: `_ForwardServer.daemon_threads = True` was already set before
    this fix, and CPython's `socketserver.ThreadingMixIn._Threads.append()`
    unconditionally skips daemon threads — so `server_close()` never actually
    joined a stuck handler here regardless of `block_on_close`. Confirmed via
    a throwaway monkeypatch (`daemon_threads = False`, `block_on_close =
    True`) that this exact scenario *does* hang indefinitely without either
    protection, which is what this test would catch if a future change
    weakened `block_on_close = False` or removed `daemon_threads = True`. The
    whole `with`-block body runs on a daemon watchdog thread so a real hang
    fails this test (via the timed `join`) instead of hanging the suite.
    """
    ssh_resource = _make_resource()

    # Channel side: a real, pollable fd that never becomes readable.
    read_fd, write_fd = os.pipe()

    channel = MagicMock()
    channel.fileno.return_value = read_fd
    channel.recv.return_value = b""

    transport = MagicMock()
    transport.open_channel.return_value = channel

    client = MagicMock()
    client.get_transport.return_value = transport

    object.__setattr__(ssh_resource, "get_connection", lambda: client)

    exited = threading.Event()
    client_sockets: list[socket.socket] = []

    def run_tunnel():
        with ssh_resource.open_ssh_tunnel_paramiko(local_port=0) as local_port:
            s = socket.create_connection(("127.0.0.1", local_port), timeout=5)
            client_sockets.append(s)
            # Send nothing: both `self.request` (this socket, server side)
            # and `channel` (the pipe) stay unreadable, so once the handler
            # thread accepts the connection and opens the channel, it parks
            # in `select()` and never returns on its own — exactly the
            # still-open-forwarded-connection scenario that deadlocks
            # `server_close()` pre-fix.
            time.sleep(0.3)
        exited.set()

    watchdog = threading.Thread(target=run_tunnel, daemon=True)
    watchdog.start()
    watchdog.join(timeout=5)

    try:
        assert exited.is_set(), (
            "open_ssh_tunnel_paramiko's context exit hung for 5s+ — "
            "server_close() likely blocked joining a handler thread stuck "
            "in select() on a still-open forwarded connection"
        )
    finally:
        for s in client_sockets:
            s.close()
        os.close(read_fd)
        os.close(write_fd)
