# trunk-ignore-all(pyright/reportAttributeAccessIssue)
# trunk-ignore-all(pyright/reportGeneralTypeIssues)
# trunk-ignore-all(pyright/reportFunctionMemberAccess)

import logging
import socket
import sys
from binascii import hexlify
from queue import Full, Queue
from select import select
from socketserver import BaseRequestHandler, TCPServer, ThreadingMixIn, UnixStreamServer

from paramiko import SSHException, Transport

from teamster.libraries.ssh.sshtunnel.errors import HandlerSSHTunnelForwarderError
from teamster.libraries.ssh.sshtunnel.utils import create_logger, generate_random_string

# Timeout (seconds) for tunnel connection (open_channel timeout)
TUNNEL_TIMEOUT = 10.0
TRACE_LEVEL = 1


class ForwardHandler(BaseRequestHandler):
    """Base handler for tunnel connections"""

    logger: logging.Logger
    ssh_transport: Transport
    remote_address = None
    info = None

    def _redirect(self, chan):
        while chan.active:
            rqst, _, _ = select([self.request, chan], [], [], 5)

            if self.request in rqst:
                data = self.request.recv(16384)

                if not data:
                    self.logger.log(
                        level=TRACE_LEVEL,
                        msg=f">>> OUT {self.info} recv empty data >>>",
                    )
                    break

                if self.logger.isEnabledFor(TRACE_LEVEL):
                    self.logger.log(
                        level=TRACE_LEVEL,
                        msg=(
                            f">>> OUT {self.info} send to {self.remote_address}: "
                            f"{hexlify(data)} >>>"
                        ),
                    )

                chan.sendall(data)

            if chan in rqst:  # else
                if not chan.recv_ready():
                    self.logger.log(
                        level=TRACE_LEVEL,
                        msg=f"<<< IN {self.info} recv is not ready <<<",
                    )
                    break

                data = chan.recv(16384)

                if self.logger.isEnabledFor(TRACE_LEVEL):
                    hex_data = hexlify(data)
                    self.logger.log(
                        level=TRACE_LEVEL,
                        msg=f"<<< IN {self.info} recv: {hex_data} <<<",
                    )

                self.request.sendall(data)

    def handle(self):
        self.info = (
            f"#{generate_random_string(5)} <-- "
            f"{self.client_address or self.server.local_address}"
        )

        src_address = self.request.getpeername()

        if not isinstance(src_address, tuple):
            src_address = ("dummy", 12345)

        try:
            chan = self.ssh_transport.open_channel(
                kind="direct-tcpip",
                dest_addr=self.remote_address,
                src_addr=src_address,
                timeout=TUNNEL_TIMEOUT,
            )
        except Exception as e:
            exc_msg = (
                "open new channel "
                + ("ssh" if isinstance(e, SSHException) else "")
                + f" error: {e}"
            )

            self.logger.log(TRACE_LEVEL, f"{self.info} {exc_msg}")
            raise HandlerSSHTunnelForwarderError(exc_msg) from e

        self.logger.log(TRACE_LEVEL, f"{self.info} connected")

        try:
            self._redirect(chan)
        except socket.error:
            # Sometimes a RST is sent and a socket error is raised, treat this
            # exception. It was seen that a 3way FIN is processed later on, so
            # no need to make an ordered close of the connection here or raise
            # the exception beyond this point...
            self.logger.log(TRACE_LEVEL, f"{self.info} sending RST")
        except Exception as e:
            self.logger.log(TRACE_LEVEL, f"{self.info} error: {repr(e)}")
        finally:
            chan.close()
            self.request.close()
            self.logger.log(TRACE_LEVEL, f"{self.info} connection closed.")


class ForwardServer(TCPServer):  # Not Threading
    """
    Non-threading version of the forward server
    """

    allow_reuse_address = True  # faster rebinding

    def __init__(self, *args, **kwargs):
        logger = kwargs.pop("logger", None)

        self.logger = logger or create_logger()
        self.tunnel_ok = Queue(1)

        TCPServer.__init__(self, *args, **kwargs)

    def handle_error(self, request, client_address):
        remote_side = self.remote_address
        local_side = request.getsockname()

        (exc_class, exc, tb) = sys.exc_info()

        self.logger.error(
            f"Could not establish connection from local {local_side} to remote "
            f"{remote_side} side of the tunnel: {exc}"
        )

        try:
            self.tunnel_ok.put(False, block=False, timeout=0.1)
        except Full:
            # wait untill tunnel_ok.get is called
            pass
        except exc:
            self.logger.error(f"unexpected internal error: {exc}")

    @property
    def local_address(self):
        return self.server_address

    @property
    def local_host(self):
        return self.server_address[0]

    @property
    def local_port(self):
        return self.server_address[1]

    @property
    def remote_address(self):
        return self.RequestHandlerClass.remote_address

    @property
    def remote_host(self):
        return self.RequestHandlerClass.remote_address[0]

    @property
    def remote_port(self):
        return self.RequestHandlerClass.remote_address[1]


class ThreadingForwardServer(ThreadingMixIn, ForwardServer):
    """
    Allow concurrent connections to each tunnel
    """

    # If True, cleanly stop threads created by ThreadingMixIn when quitting
    # This value is overrides by SSHTunnelForwarder.daemon_forward_servers
    daemon_threads = True


class StreamForwardServer(UnixStreamServer):
    """
    Serve over domain sockets (does not work on Windows)
    """

    def __init__(self, *args, **kwargs):
        logger = kwargs.pop("logger", None)

        self.logger = logger or create_logger()
        self.tunnel_ok = Queue(1)

        UnixStreamServer.__init__(self, *args, **kwargs)

    @property
    def local_address(self):
        return self.server_address

    @property
    def local_host(self):
        return None

    @property
    def local_port(self):
        return None

    @property
    def remote_address(self):
        return self.RequestHandlerClass.remote_address

    @property
    def remote_host(self):
        return self.RequestHandlerClass.remote_address[0]

    @property
    def remote_port(self):
        return self.RequestHandlerClass.remote_address[1]


class ThreadingStreamForwardServer(ThreadingMixIn, StreamForwardServer):
    """
    Allow concurrent connections to each tunnel
    """

    # If True, cleanly stop threads created by ThreadingMixIn when quitting
    # This value is overrides by SSHTunnelForwarder.daemon_forward_servers
    daemon_threads = True
