# https://github.com/pahaz/sshtunnel/blob/master/sshtunnel.py
# trunk-ignore-all(pyright/reportArgumentType)
# trunk-ignore-all(pyright/reportCallIssue)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
*sshtunnel* - Initiate SSH tunnels via a remote gateway.

``sshtunnel`` works by opening a port forwarding SSH connection in the
background, using threads.

The connection(s) are closed when explicitly calling the
:meth:`SSHTunnelForwarder.stop` method or using it as a context.

"""

import logging
import os
import socket
from binascii import hexlify
from queue import Empty
from threading import Thread

from paramiko import (
    Agent,
    AuthenticationException,
    DSSKey,
    ECDSAKey,
    Ed25519Key,
    PasswordRequiredException,
    PKey,
    ProxyCommand,
    RSAKey,
    SSHConfig,
    SSHException,
    Transport,
)

from teamster.libraries.ssh.sshtunnel.errors import (
    BaseSSHTunnelForwarderError,
    HandlerSSHTunnelForwarderError,
)
from teamster.libraries.ssh.sshtunnel.handlers import (
    ForwardHandler,
    ForwardServer,
    StreamForwardServer,
    ThreadingForwardServer,
    ThreadingStreamForwardServer,
)
from teamster.libraries.ssh.sshtunnel.utils import (
    address_to_str,
    check_address,
    check_addresses,
    check_host,
    check_port,
    create_logger,
    remove_none_values,
)

__author__ = "pahaz"

# Timeout (seconds) for transport socket (`socket.settimeout`)
# `None` may cause a block of transport thread
SSH_TIMEOUT = 0.1

# Timeout (seconds) for tunnel connection (`open_channel` timeout)
TUNNEL_TIMEOUT = 10.0

# logging
DEFAULT_LOGLEVEL = logging.ERROR
TRACE_LEVEL = 1

logging.addLevelName(TRACE_LEVEL, "TRACE")

# Path of optional ssh configuration file
DEFAULT_SSH_DIRECTORY = "~/.ssh"
SSH_CONFIG_FILE = os.path.join(DEFAULT_SSH_DIRECTORY, "config")


class SSHTunnelForwarder(object):
    """
    **SSH tunnel class**

        - Initialize a SSH tunnel to a remote host according to the input
          arguments

        - Optionally:
            + Read an SSH configuration file (typically ``~/.ssh/config``)
            + Load keys from a running SSH agent (i.e. Pageant, GNOME Keyring)

    Raises:

        :class:`.BaseSSHTunnelForwarderError`:
            raised by SSHTunnelForwarder class methods

        :class:`.HandlerSSHTunnelForwarderError`:
            raised by tunnel forwarder threads

            .. note::
                    ``mute_exceptions`` may be used to silence most exceptions raised
                    from this class

    Keyword Arguments:

        ssh_address_or_host (tuple or str):
            IP or hostname of ``REMOTE GATEWAY``. It may be a two-element
            tuple (``str``, ``int``) representing IP and port respectively,
            or a ``str`` representing the IP address only

            .. versionadded:: 0.0.4

        ssh_config_file (str):
            SSH configuration file that will be read. If explicitly set to
            ``None``, parsing of this configuration is omitted

            Default: :const:`SSH_CONFIG_FILE`

            .. versionadded:: 0.0.4

        ssh_host_key (str):
            Representation of a line in an OpenSSH-style "known hosts"
            file.

            ``REMOTE GATEWAY``'s key fingerprint will be compared to this
            host key in order to prevent against SSH server spoofing.
            Important when using passwords in order not to accidentally
            do a login attempt to a wrong (perhaps an attacker's) machine

        ssh_username (str):
            Username to authenticate as in ``REMOTE SERVER``

            Default: current local user name

        ssh_password (str):
            Text representing the password used to connect to ``REMOTE
            SERVER`` or for unlocking a private key.

            .. note::
                Avoid coding secret password directly in the code, since this
                may be visible and make your service vulnerable to attacks

        ssh_port (int):
            Optional port number of the SSH service on ``REMOTE GATEWAY``,
            when `ssh_address_or_host`` is a ``str`` representing the
            IP part of ``REMOTE GATEWAY``'s address

            Default: 22

        ssh_pkey (str or paramiko.PKey):
            **Private** key file name (``str``) to obtain the public key
            from or a **public** key (:class:`paramiko.pkey.PKey`)

        ssh_private_key_password (str):
            Password for an encrypted ``ssh_pkey``

            .. note::
                Avoid coding secret password directly in the code, since this
                may be visible and make your service vulnerable to attacks

        ssh_proxy (socket-like object or tuple):
            Proxy where all SSH traffic will be passed through.
            It might be for example a :class:`paramiko.proxy.ProxyCommand`
            instance.
            See either the :class:`paramiko.transport.Transport`'s sock
            parameter documentation or ``ProxyCommand`` in ``ssh_config(5)``
            for more information.

            It is also possible to specify the proxy address as a tuple of
            type (``str``, ``int``) representing proxy's IP and port

            .. note::
                Ignored if ``ssh_proxy_enabled`` is False

            .. versionadded:: 0.0.5

        ssh_proxy_enabled (boolean):
            Enable/disable SSH proxy. If True and user's
            ``ssh_config_file`` contains a ``ProxyCommand`` directive
            that matches the specified ``ssh_address_or_host``,
            a :class:`paramiko.proxy.ProxyCommand` object will be created where
            all SSH traffic will be passed through

            Default: ``True``

            .. versionadded:: 0.0.4

        local_bind_address (tuple):
            Local tuple in the format (``str``, ``int``) representing the
            IP and port of the local side of the tunnel. Both elements in
            the tuple are optional so both ``('', 8000)`` and
            ``('10.0.0.1', )`` are valid values

            Default: ``('0.0.0.0', RANDOM_PORT)``

            .. versionchanged:: 0.0.8
                Added the ability to use a UNIX domain socket as local bind
                address

        local_bind_addresses (list[tuple]):
            In case more than one tunnel is established at once, a list
            of tuples (in the same format as ``local_bind_address``)
            can be specified, such as [(ip1, port_1), (ip_2, port2), ...]

            Default: ``[local_bind_address]``

            .. versionadded:: 0.0.4

        remote_bind_address (tuple):
            Remote tuple in the format (``str``, ``int``) representing the
            IP and port of the remote side of the tunnel.

        remote_bind_addresses (list[tuple]):
            In case more than one tunnel is established at once, a list
            of tuples (in the same format as ``remote_bind_address``)
            can be specified, such as [(ip1, port_1), (ip_2, port2), ...]

            Default: ``[remote_bind_address]``

            .. versionadded:: 0.0.4

        allow_agent (boolean):
            Enable/disable load of keys from an SSH agent

            Default: ``True``

            .. versionadded:: 0.0.8

        host_pkey_directories (list):
            Look for pkeys in folders on this list, for example ['~/.ssh'].

            Default: ``None`` (disabled)

            .. versionadded:: 0.1.4

        compression (boolean):
            Turn on/off transport compression. By default compression is
            disabled since it may negatively affect interactive sessions

            Default: ``False``

            .. versionadded:: 0.0.8

        logger (logging.Logger):
            logging instance for sshtunnel and paramiko

            Default: :class:`logging.Logger` instance with a single
            :class:`logging.StreamHandler` handler and
            :const:`DEFAULT_LOGLEVEL` level

            .. versionadded:: 0.0.3

        mute_exceptions (boolean):
            Allow silencing :class:`BaseSSHTunnelForwarderError` or
            :class:`HandlerSSHTunnelForwarderError` exceptions when enabled

            Default: ``False``

            .. versionadded:: 0.0.8

        set_keepalive (float):
            Interval in seconds defining the period in which, if no data
            was sent over the connection, a *'keepalive'* packet will be
            sent (and ignored by the remote host). This can be useful to
            keep connections alive over a NAT. You can set to 0.0 for
            disable keepalive.

            Default: 5.0 (no keepalive packets are sent)

            .. versionadded:: 0.0.7

        threaded (boolean):
            Allow concurrent connections over a single tunnel

            Default: ``True``

            .. versionadded:: 0.0.3

    Attributes:

        tunnel_is_up (dict):
            Describe whether or not the other side of the tunnel was reported
            to be up (and we must close it) or not (skip shutting down that
            tunnel)

            .. note::
                This attribute should not be modified

            .. note::
                When :attr:`.skip_tunnel_checkup` is disabled or the local bind
                is a UNIX socket, the value will always be ``True``

            **Example**::

                {('127.0.0.1', 55550): True,   # this tunnel is up
                 ('127.0.0.1', 55551): False}  # this one isn't

            where 55550 and 55551 are the local bind ports

        skip_tunnel_checkup (boolean):
            Disable tunnel checkup (default for backwards compatibility).

            .. versionadded:: 0.1.0

    """

    skip_tunnel_checkup = True

    # This option affects the `ForwardServer` and all his threads
    daemon_forward_servers = True  #: flag tunnel threads in daemon mode

    # This option affect only `Transport` thread
    daemon_transport = True  #: flag SSH transport thread in daemon mode

    def local_is_up(self, target):
        """
        Check if a tunnel is up (remote target's host is reachable on TCP
        target's port)

        Arguments:
            target (tuple):
                tuple of type (``str``, ``int``) indicating the listen IP
                address and port
        Return:
            boolean

        .. deprecated:: 0.1.0
            Replaced by :meth:`.check_tunnels()` and :attr:`.tunnel_is_up`
        """
        try:
            check_address(target)
        except ValueError:
            self.logger.warning(
                "Target must be a tuple (IP, port), where IP "
                'is a string (i.e. "192.168.0.1") and port is '
                "an integer (i.e. 40000). Alternatively "
                "target can be a valid UNIX domain socket."
            )
            return False

        self.check_tunnels()

        return self.tunnel_is_up.get(target, True)

    def check_tunnels(self):
        """
        Check that if all tunnels are established and populates
        :attr:`.tunnel_is_up`
        """
        skip_tunnel_checkup = self.skip_tunnel_checkup

        try:
            # force tunnel check at this point
            self.skip_tunnel_checkup = False
            for _srv in self._server_list:
                self._check_tunnel(_srv)
        finally:
            self.skip_tunnel_checkup = skip_tunnel_checkup  # roll it back

    def _check_tunnel(self, _srv):
        """Check if tunnel is already established"""
        if self.skip_tunnel_checkup:
            self.tunnel_is_up[_srv.local_address] = True
            return

        self.logger.info(f"Checking tunnel to: {_srv.remote_address}")

        if isinstance(_srv.local_address, str):  # UNIX stream
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        s.settimeout(TUNNEL_TIMEOUT)

        try:
            # Windows raises WinError 10049 if trying to connect to 0.0.0.0
            connect_to = (
                ("127.0.0.1", _srv.local_port)
                if _srv.local_host == "0.0.0.0"
                else _srv.local_address
            )

            s.connect(connect_to)

            self.logger.debug(f"Tunnel to {_srv.remote_address} is DOWN")
            self.tunnel_is_up[_srv.local_address] = _srv.tunnel_ok.get(
                timeout=TUNNEL_TIMEOUT * 1.1
            )
        except socket.error:
            self.logger.debug(f"Tunnel to {_srv.remote_address} is DOWN")
            self.tunnel_is_up[_srv.local_address] = False
        except Empty:
            self.logger.debug(f"Tunnel to {_srv.remote_address} is UP")
            self.tunnel_is_up[_srv.local_address] = True
        finally:
            s.close()

    def _make_ssh_forward_handler_class(self, remote_address_):
        """
        Make SSH Handler class
        """

        class Handler(ForwardHandler):
            remote_address = remote_address_
            ssh_transport = self._transport
            logger = self.logger

        return Handler

    def _make_ssh_forward_server_class(self, local_bind_address, handler):
        if self._threaded:
            forward_server = ThreadingForwardServer(
                local_bind_address, handler, self.logger
            )

            forward_server.daemon_threads = self.daemon_forward_servers
            return forward_server
        else:
            return ForwardServer(local_bind_address, handler, self.logger)

    def _make_stream_ssh_forward_server_class(self, local_bind_address, handler):
        if self._threaded:
            forward_server = ThreadingStreamForwardServer(
                local_bind_address, handler, self.logger
            )

            forward_server.daemon_threads = self.daemon_forward_servers
            return forward_server
        else:
            return StreamForwardServer(local_bind_address, handler, self.logger)

    def _make_ssh_forward_server(self, remote_address, local_bind_address):
        """
        Make SSH forward proxy Server class
        """
        handler = self._make_ssh_forward_handler_class(remote_address)

        try:
            if isinstance(local_bind_address, str):
                ssh_forward_server = self._make_stream_ssh_forward_server_class(
                    local_bind_address=local_bind_address, handler=handler
                )
            else:
                ssh_forward_server = self._make_ssh_forward_server_class(
                    local_bind_address=local_bind_address, handler=handler
                )

            if ssh_forward_server:
                self._server_list.append(ssh_forward_server)
                self.tunnel_is_up[ssh_forward_server.server_address] = False
            else:
                self._raise(
                    exception=BaseSSHTunnelForwarderError,
                    reason=(
                        f"Problem setting up ssh {address_to_str(local_bind_address)} "
                        f"<> {address_to_str(remote_address)} forwarder. You can "
                        "suppress this exception by using the `mute_exceptions` "
                        "argument"
                    ),
                )
        except IOError:
            self._raise(
                exception=BaseSSHTunnelForwarderError,
                reason=(
                    f"Couldn't open tunnel {address_to_str(local_bind_address)} <> "
                    f"{address_to_str(remote_address)} might be in use or destination "
                    "not reachable"
                ),
            )

    def __init__(
        self,
        ssh_address_or_host: tuple | str,
        ssh_config_file: str = SSH_CONFIG_FILE,
        ssh_host_key: str | None = None,
        ssh_password: str | None = None,
        ssh_port: int | None = 22,
        ssh_pkey=None,
        ssh_private_key_password=None,
        ssh_proxy=None,
        ssh_proxy_enabled: bool = True,
        ssh_username=None,
        local_bind_address=None,
        local_bind_addresses=None,
        logger: logging.Logger | None = None,
        mute_exceptions: bool = False,
        remote_bind_address=None,
        remote_bind_addresses=None,
        set_keepalive: int = 5,
        threaded: bool = True,  # old version False
        compression=None,
        allow_agent: bool = True,  # look for keys from an SSH agent
        host_pkey_directories=None,  # look for keys in ~/.ssh
    ):
        self.logger = logger or create_logger()

        self.ssh_host_key = ssh_host_key
        self.set_keepalive = set_keepalive
        self._server_list = []  # reset server list
        self.tunnel_is_up = {}  # handle tunnel status
        self._threaded = threaded
        self.is_alive = False
        self._raise_fwd_exc = not mute_exceptions

        if isinstance(ssh_address_or_host, tuple):
            check_address(ssh_address_or_host)
            (ssh_host, ssh_port) = ssh_address_or_host
        else:
            ssh_host = ssh_address_or_host

        # remote binds
        self._remote_binds = self._get_binds(
            remote_bind_address, remote_bind_addresses, is_remote=True
        )

        # local binds
        self._local_binds = self._get_binds(local_bind_address, local_bind_addresses)
        self._local_binds = self._consolidate_binds(
            self._local_binds, self._remote_binds
        )

        (
            self.ssh_host,
            self.ssh_username,
            ssh_pkey,  # still needs to go through _consolidate_auth
            self.ssh_port,
            self.ssh_proxy,
            self.compression,
        ) = self._read_ssh_config(
            ssh_host,
            ssh_config_file,
            ssh_username,
            ssh_pkey,
            ssh_port,
            ssh_proxy if ssh_proxy_enabled else None,
            compression,
        )

        (self.ssh_password, self.ssh_pkeys) = self._consolidate_auth(
            ssh_password=ssh_password,
            ssh_pkey=ssh_pkey,
            ssh_pkey_password=ssh_private_key_password,
            allow_agent=allow_agent,
            host_pkey_directories=host_pkey_directories,
        )

        check_host(self.ssh_host)
        check_port(self.ssh_port)

        self.logger.info(
            f"Connecting to gateway: {self.ssh_host}:{self.ssh_port} as user "
            f"'{self.ssh_username}'"
        )

        self.logger.debug(f"Concurrent connections allowed: {self._threaded}")

    def _read_ssh_config(
        self,
        ssh_host,
        ssh_config_file,
        ssh_username=None,
        ssh_pkey=None,
        ssh_port=None,
        ssh_proxy=None,
        compression=None,
    ):
        """
        Read ssh_config_file and tries to look for user (ssh_username),
        identityfile (ssh_pkey), port (ssh_port) and proxycommand
        (ssh_proxy) entries for ssh_host
        """
        ssh_config = SSHConfig()
        if not ssh_config_file:  # handle case where it's an empty string
            ssh_config_file = None

        # Try to read SSH_CONFIG_FILE
        try:
            # open the ssh config file
            with open(file=os.path.expanduser(ssh_config_file), mode="r") as f:
                ssh_config.parse(f)

            # looks for information for the destination system
            hostname_info = ssh_config.lookup(ssh_host)

            # gather settings for user, port and identity file
            # last resort: use the 'login name' of the user
            ssh_username = ssh_username or hostname_info.get("user")
            ssh_pkey = ssh_pkey or hostname_info.get("identityfile", [None])[0]
            ssh_host = hostname_info.get("hostname")
            ssh_port = ssh_port or hostname_info.get("port")

            proxycommand = hostname_info.get("proxycommand")
            ssh_proxy = ssh_proxy or (
                ProxyCommand(proxycommand) if proxycommand else None
            )

            if compression is None:
                compression = hostname_info.get("compression", "")
                compression = True if compression.upper() == "YES" else False
        except IOError:
            self.logger.warning(
                f"Could not read SSH configuration file: {ssh_config_file}"
            )
        except (AttributeError, TypeError):  # ssh_config_file is None
            self.logger.info("Skipping loading of ssh configuration file")

        return (
            ssh_host,
            ssh_username,
            ssh_pkey,
            int(ssh_port) if ssh_port else 22,  # fallback value
            ssh_proxy,
            compression,
        )

    def get_agent_keys(self):
        """Load public keys from any available SSH agent

        Arguments:
            logger (Optional[logging.Logger])

        Return:
            list
        """
        paramiko_agent = Agent()

        agent_keys = paramiko_agent.get_keys()

        self.logger.info(f"{len(agent_keys)} keys loaded from agent")
        return list(agent_keys)

    def get_keys(self, host_pkey_directories=None, allow_agent=False):
        """
        Load public keys from any available SSH agent or local
        .ssh directory.

        Arguments:
            logger (Optional[logging.Logger])

            host_pkey_directories (Optional[list[str]]):
                List of local directories where host SSH pkeys in the format
                "id_*" are searched. For example, ['~/.ssh']

                .. versionadded:: 0.1.0

            allow_agent (Optional[boolean]):
                Whether or not load keys from agent

                Default: False

        Return:
            list
        """
        keys: list = self.get_agent_keys() if allow_agent else []

        if host_pkey_directories is None:
            host_pkey_directories = [DEFAULT_SSH_DIRECTORY]

        paramiko_key_types = {
            "rsa": RSAKey,
            "dsa": DSSKey,
            "ecdsa": ECDSAKey,
            "ed25519": Ed25519Key,
        }

        for directory in host_pkey_directories:
            for keytype in paramiko_key_types.keys():
                ssh_pkey_expanded = os.path.expanduser(
                    os.path.join(directory, f"id_{keytype}")
                )

                try:
                    if os.path.isfile(ssh_pkey_expanded):
                        ssh_pkey = self.read_private_key_file(
                            pkey_file=ssh_pkey_expanded,
                            key_type=paramiko_key_types[keytype],
                        )

                        if ssh_pkey:
                            keys.append(ssh_pkey)
                except OSError as exc:
                    self.logger.warning(
                        f"Private key file {ssh_pkey_expanded} check error: {exc}"
                    )

        self.logger.info(f"{len(keys)} key(s) loaded")
        return keys

    def _consolidate_binds(self, local_binds, remote_binds):
        """
        Fill local_binds with defaults when no value/s were specified,
        leaving paramiko to decide in which local port the tunnel will be open
        """
        count = len(remote_binds) - len(local_binds)

        if count < 0:
            raise ValueError(
                "Too many local bind addresses "
                "(local_bind_addresses > remote_bind_addresses)"
            )

        local_binds.extend([("0.0.0.0", 0) for x in range(count)])

        return local_binds

    def _consolidate_auth(
        self,
        ssh_password=None,
        ssh_pkey=None,
        ssh_pkey_password=None,
        allow_agent=True,
        host_pkey_directories=None,
    ):
        """
        Get sure authentication information is in place.
        ``ssh_pkey`` may be of classes:
            - ``str`` - in this case it represents a private key file; public
            key will be obtained from it
            - ``paramiko.Pkey`` - it will be transparently added to loaded keys

        """
        ssh_loaded_pkeys = self.get_keys(
            host_pkey_directories=host_pkey_directories, allow_agent=allow_agent
        )

        if isinstance(ssh_pkey, str):
            ssh_pkey_expanded = os.path.expanduser(ssh_pkey)

            if os.path.exists(ssh_pkey_expanded):
                ssh_pkey = self.read_private_key_file(
                    pkey_file=ssh_pkey_expanded,
                    pkey_password=ssh_pkey_password or ssh_password,
                )
            else:
                self.logger.warning(f"Private key file not found: {ssh_pkey}")

        if isinstance(ssh_pkey, PKey):
            ssh_loaded_pkeys.insert(0, ssh_pkey)

        if not ssh_password and not ssh_loaded_pkeys:
            raise ValueError("No password or public key available!")

        return (ssh_password, ssh_loaded_pkeys)

    def _raise(self, exception=BaseSSHTunnelForwarderError, reason=None):
        if self._raise_fwd_exc:
            raise exception(reason)
        else:
            self.logger.error(repr(exception(reason)))

    def _get_transport(self):
        """Return the SSH transport to the remote gateway"""
        if self.ssh_proxy:
            if isinstance(self.ssh_proxy, ProxyCommand):
                proxy_repr = repr(self.ssh_proxy.cmd[1])
            else:
                proxy_repr = repr(self.ssh_proxy)

            self.logger.debug(f"Connecting via proxy: {proxy_repr}")
            _socket = self.ssh_proxy
        else:
            _socket = (self.ssh_host, self.ssh_port)

        if isinstance(_socket, socket.socket):
            _socket.settimeout(SSH_TIMEOUT)
            _socket.connect((self.ssh_host, self.ssh_port))

        transport = Transport(sock=_socket)

        sock = transport.sock

        if isinstance(sock, socket.socket):
            sock.settimeout(SSH_TIMEOUT)

        transport.set_keepalive(self.set_keepalive)
        transport.use_compression(compress=self.compression)
        transport.daemon = self.daemon_transport

        # try to solve https://github.com/paramiko/paramiko/issues/1181
        # transport.banner_timeout = 200
        if isinstance(sock, socket.socket):
            sock_timeout = sock.gettimeout()
            sock_info = repr((sock.family, sock.type, sock.proto))

            self.logger.debug(
                f"Transport socket info: {sock_info}, timeout={sock_timeout}"
            )

        return transport

    def _create_tunnels(self):
        """
        Create SSH tunnels on top of a transport to the remote gateway
        """
        if not self.is_active:
            try:
                self._connect_to_gateway()
            except socket.gaierror:  # raised by paramiko.Transport
                self.logger.error(
                    f"Could not resolve IP address for {self.ssh_host}, aborting!"
                )
                return
            except (SSHException, socket.error) as e:
                self.logger.error(
                    f"Could not connect to gateway {self.ssh_host}:{self.ssh_port} : "
                    f"{e.args[0]}"
                )
                return

        for rem, loc in zip(self._remote_binds, self._local_binds):
            try:
                self._make_ssh_forward_server(rem, loc)
            except BaseSSHTunnelForwarderError as e:
                self.logger.error(f"Problem setting SSH Forwarder up: {e.value}")

    def _get_binds(self, bind_address, bind_addresses, is_remote=False):
        addr_kind = "remote" if is_remote else "local"

        if not bind_address and not bind_addresses:
            if is_remote:
                raise ValueError(
                    f"No {addr_kind} bind addresses specified. Use "
                    f"'{addr_kind}_bind_address' or '{addr_kind}_bind_addresses' "
                    "argument"
                )
            else:
                return []
        elif bind_address and bind_addresses:
            raise ValueError(
                f"You can't use both '{addr_kind}_bind_address' and "
                f"'{addr_kind}_bind_addresses' arguments. Use one of "
                "them."
            )

        if bind_address:
            bind_addresses = [bind_address]

        if not is_remote:
            # Add random port if missing in local bind
            for i, local_bind in enumerate(bind_addresses):
                if isinstance(local_bind, tuple) and len(local_bind) == 1:
                    bind_addresses[i] = (local_bind[0], 0)

        check_addresses(bind_addresses, is_remote)

        return bind_addresses

    def read_private_key_file(self, pkey_file, pkey_password=None, key_type=None):
        """
        Get SSH Public key from a private key file, given an optional password

        Arguments:
            pkey_file (str):
                File containing a private key (RSA, DSS or ECDSA)
        Keyword Arguments:
            pkey_password (Optional[str]):
                Password to decrypt the private key
            logger (Optional[logging.Logger])
        Return:
            paramiko.Pkey
        """
        ssh_pkey = None
        key_types = (RSAKey, DSSKey, ECDSAKey, Ed25519Key)

        for pkey_class in (key_type,) if key_type else key_types:
            try:
                ssh_pkey = pkey_class.from_private_key_file(
                    pkey_file, password=pkey_password
                )

                self.logger.debug(
                    f"Private key file ({pkey_file}, {pkey_class}) successfully loaded"
                )
                break
            except PasswordRequiredException:
                self.logger.error(f"Password is required for key {pkey_file}")
                break
            except SSHException:
                self.logger.debug(
                    f"Private key file ({pkey_file}) could not be loaded as type "
                    f"{pkey_class} or bad password"
                )

        return ssh_pkey

    def start(self):
        """Start the SSH tunnels"""
        if self.is_alive:
            self.logger.warning("Already started!")
            return

        self._create_tunnels()

        if not self.is_active:
            self._raise(
                exception=BaseSSHTunnelForwarderError,
                reason="Could not establish session to SSH gateway",
            )

        for _srv in self._server_list:
            thread = Thread(
                target=self._serve_forever_wrapper,
                args=(_srv,),
                name=f"Srv-{address_to_str(_srv.local_port)}",
            )

            thread.daemon = self.daemon_forward_servers
            thread.start()

            self._check_tunnel(_srv)

        self.is_alive = any(self.tunnel_is_up.values())

        if not self.is_alive:
            self._raise(
                exception=HandlerSSHTunnelForwarderError,
                reason="An error occurred while opening tunnels.",
            )

    def stop(self, force=False):
        """
        Shut the tunnel down. By default we are always waiting until closing
        all connections. You can use `force=True` to force close connections

        Keyword Arguments:
            force (bool):
                Force close current connections

                Default: False

                .. versionadded:: 0.2.2

        .. note:: This **had** to be handled with care before ``0.1.0``:

            - if a port redirection is opened
            - the destination is not reachable
            - we attempt a connection to that tunnel (``SYN`` is sent and
              acknowledged, then a ``FIN`` packet is sent and never
              acknowledged... weird)
            - we try to shutdown: it will not succeed until ``FIN_WAIT_2`` and
              ``CLOSE_WAIT`` time out.

        .. note::
            Handle these scenarios with :attr:`.tunnel_is_up`: if False, server
            ``shutdown()`` will be skipped on that tunnel
        """
        self.logger.info("Closing all open connections...")
        opened_address_text = (
            ", ".join((address_to_str(k.local_address) for k in self._server_list))
            or "None"
        )
        self.logger.debug("Listening tunnels: " + opened_address_text)
        self._stop_transport(force=force)
        self._server_list = []  # reset server list
        self.tunnel_is_up = {}  # reset tunnel status

    def close(self):
        """Stop the an active tunnel, alias to :meth:`.stop`"""
        self.stop()

    def restart(self):
        """Restart connection to the gateway and tunnels"""
        self.stop()
        self.start()

    def _connect_to_gateway(self):
        """
        Open connection to SSH gateway
         - First try with all keys loaded from an SSH agent (if allowed)
         - Then with those passed directly or read from ~/.ssh/config
         - As last resort, try with a provided password
        """
        for key in self.ssh_pkeys:
            self.logger.debug(
                f"Trying to log in with key: {hexlify(key.get_fingerprint())}"
            )

            try:
                self._transport = self._get_transport()
                self._transport.connect(
                    hostkey=self.ssh_host_key, username=self.ssh_username, pkey=key
                )

                if self._transport.is_alive:
                    return
            except AuthenticationException:
                self.logger.debug("Authentication error")
                self._stop_transport()

        if self.ssh_password:  # avoid conflict using both pass and pkey
            self.logger.debug("Trying to log in with password")

            try:
                self._transport = self._get_transport()
                self._transport.connect(
                    hostkey=self.ssh_host_key,
                    username=self.ssh_username,
                    password=self.ssh_password,
                )

                if self._transport.is_alive:
                    return
            except AuthenticationException as e:
                self.logger.error("Authentication error")
                self._stop_transport()
                raise e

        if not self._transport.is_alive:
            raise SSHException("Could not open connection to gateway")

    def _serve_forever_wrapper(self, _srv, poll_interval=0.1):
        """
        Wrapper for the server created for a SSH forward
        """
        self.logger.info(
            f"Opening tunnel: {address_to_str(_srv.local_address)} <> "
            f"{address_to_str(_srv.remote_address)}"
        )
        _srv.serve_forever(poll_interval)  # blocks until finished

        self.logger.info(
            f"Tunnel: {address_to_str(_srv.local_address)} <> "
            f"{address_to_str(_srv.remote_address)} released"
        )

    def _stop_transport(self, force=False):
        """Close the underlying transport when nothing more is needed"""
        try:
            self._check_is_started()
        except (BaseSSHTunnelForwarderError, HandlerSSHTunnelForwarderError) as e:
            self.logger.warning(e)

        if force and self.is_active:
            # don't wait connections
            self.logger.info("Closing ssh transport")
            self._transport.close()
            self._transport.stop_thread()

        for _srv in self._server_list:
            status = "up" if self.tunnel_is_up[_srv.local_address] else "down"

            self.logger.info(
                f"Shutting down tunnel: {address_to_str(_srv.local_address)} <> "
                f"{address_to_str(_srv.remote_address)} ({status})"
            )

            _srv.shutdown()
            _srv.server_close()

            # clean up the UNIX domain socket if we're using one
            if isinstance(_srv, StreamForwardServer):
                try:
                    os.unlink(_srv.local_address)
                except Exception as e:
                    self.logger.error(
                        f"Unable to unlink socket {_srv.local_address}: {repr(e)}"
                    )

        self.is_alive = False

        if self.is_active:
            self.logger.info("Closing ssh transport")
            self._transport.close()
            self._transport.stop_thread()

        self.logger.debug("Transport is closed")

    @property
    def local_bind_port(self):
        # BACKWARDS COMPATIBILITY
        self._check_is_started()
        if len(self._server_list) != 1:
            raise BaseSSHTunnelForwarderError(
                "Use .local_bind_ports property for more than one tunnel"
            )
        return self.local_bind_ports[0]

    @property
    def local_bind_host(self):
        # BACKWARDS COMPATIBILITY
        self._check_is_started()
        if len(self._server_list) != 1:
            raise BaseSSHTunnelForwarderError(
                "Use .local_bind_hosts property for more than one tunnel"
            )
        return self.local_bind_hosts[0]

    @property
    def local_bind_address(self):
        # BACKWARDS COMPATIBILITY
        self._check_is_started()
        if len(self._server_list) != 1:
            raise BaseSSHTunnelForwarderError(
                "Use .local_bind_addresses property for more than one tunnel"
            )
        return self.local_bind_addresses[0]

    @property
    def local_bind_ports(self):
        """
        Return a list containing the ports of local side of the TCP tunnels
        """
        self._check_is_started()
        return [
            _server.local_port
            for _server in self._server_list
            if _server.local_port is not None
        ]

    @property
    def local_bind_hosts(self):
        """
        Return a list containing the IP addresses listening for the tunnels
        """
        self._check_is_started()
        return [
            _server.local_host
            for _server in self._server_list
            if _server.local_host is not None
        ]

    @property
    def local_bind_addresses(self):
        """
        Return a list of (IP, port) pairs for the local side of the tunnels
        """
        self._check_is_started()
        return [_server.local_address for _server in self._server_list]

    @property
    def tunnel_bindings(self):
        """
        Return a dictionary containing the active local<>remote tunnel_bindings
        """
        return dict(
            (_server.remote_address, _server.local_address)
            for _server in self._server_list
            if self.tunnel_is_up[_server.local_address]
        )

    @property
    def is_active(self):
        """Return True if the underlying SSH transport is up"""
        if "_transport" in self.__dict__ and self._transport.is_active():
            return True
        return False

    def _check_is_started(self):
        if not self.is_active:  # underlying transport not alive
            raise BaseSSHTunnelForwarderError(
                "Server is not started. Please .start() first!"
            )

        if not self.is_alive:
            raise HandlerSSHTunnelForwarderError(
                "Tunnels are not started. Please .start() first!"
            )

    def __str__(self):
        credentials = {
            "password": self.ssh_password,
            "pkeys": [
                (key.get_name(), hexlify(key.get_fingerprint()))
                for key in self.ssh_pkeys
            ]
            if any(self.ssh_pkeys)
            else None,
        }

        remove_none_values(credentials)

        template = os.linesep.join(
            [
                "{0} object",
                "ssh gateway: {1}:{2}",
                "proxy: {3}",
                "username: {4}",
                "authentication: {5}",
                "hostkey: {6}",
                "status: {7}started",
                "keepalive messages: {8}",
                "tunnel connection check: {9}",
                "concurrent connections: {10}allowed",
                "compression: {11}requested",
                "logging level: {12}",
                "local binds: {13}",
                "remote binds: {14}",
            ]
        )

        return template.format(
            self.__class__,
            self.ssh_host,
            self.ssh_port,
            self.ssh_proxy.cmd[1] if self.ssh_proxy else "no",
            self.ssh_username,
            credentials,
            self.ssh_host_key if self.ssh_host_key else "not checked",
            "" if self.is_alive else "not ",
            "disabled" if not self.set_keepalive else f"every {self.set_keepalive} sec",
            "disabled" if self.skip_tunnel_checkup else "enabled",
            "" if self._threaded else "not ",
            "" if self.compression else "not ",
            logging.getLevelName(self.logger.level),
            self._local_binds,
            self._remote_binds,
        )

    def __repr__(self):
        return self.__str__()

    def __enter__(self):
        try:
            self.start()
            return self
        except KeyboardInterrupt:
            self.__exit__()

    def __exit__(self, *args):
        self.stop(force=True)

    def __del__(self):
        if self.is_active or self.is_alive:
            self.logger.warning(
                "It looks like you didn't call the .stop() before "
                "the SSHTunnelForwarder obj was collected by "
                "the garbage collector! Running .stop(force=True)"
            )
            self.stop(force=True)
