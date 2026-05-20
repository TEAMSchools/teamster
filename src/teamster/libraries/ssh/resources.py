import socket
import subprocess
import threading
import time
from pathlib import Path
from stat import S_ISDIR, S_ISREG

from cryptography.hazmat.primitives import hashes
from dagster_shared import check
from dagster_ssh import SSHResource as DagsterSSHResource
from paramiko import RSAKey, SFTPAttributes, SFTPClient, SSHClient, Transport
from paramiko.ssh_exception import NoValidConnectionsError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

# Serializes mutation of `Transport._preferred_keys`, `Transport._key_info`,
# and `RSAKey.HASHES` across concurrent `enable_legacy_rsa` connects in the
# same process — without it, two threads can interleave save/restore and leak
# `ssh-rsa` past the legacy resource's call (Thread B captures A's mutated
# value as "original" and restores to it).
_PREFERRED_KEYS_LOCK = threading.Lock()


class SSHTunnelError(Exception):
    """Raised when the sshpass tunnel subprocess emits unexpected stdout."""


class SSHResource(DagsterSSHResource):
    tunnel_remote_host: str | None = None
    test: bool = False
    # paramiko 5.0 dropped `ssh-rsa` (SHA-1 RSA host keys) from its default
    # _preferred_keys. Set True to re-enable ssh-rsa for servers that only
    # advertise it (otherwise KEX negotiation fails with IncompatiblePeer).
    enable_legacy_rsa: bool = False

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential_jitter(initial=2, max=30),
        # Only retry true transients. SSHException is too broad — it covers
        # IncompatiblePeer / BadHostKeyException / BadAuthenticationType, which
        # are deterministic config failures that will fail identically on every
        # attempt and burn ~30s per call.
        retry=retry_if_exception_type(
            (
                NoValidConnectionsError,
                TimeoutError,
                socket.gaierror,
                ConnectionResetError,
            )
        ),
        reraise=True,
    )
    def get_connection(self) -> SSHClient:
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
                return super().get_connection()
            finally:
                Transport._preferred_keys = original_preferred_keys
                Transport._key_info = original_key_info
                RSAKey.HASHES = original_rsa_hashes

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

    def open_ssh_tunnel(self) -> subprocess.Popen[bytes]:
        # trunk-ignore(bandit/B603): static argv, no shell; inputs are EnvVar resource config
        ssh_tunnel = subprocess.Popen(
            args=[
                "sshpass",
                (
                    f"-p{self.password}"
                    if self.test
                    else "-f/etc/secret-volume/powerschool_ssh_password.txt"
                ),
                "ssh",
                self.remote_host,
                f"-p{self.remote_port}",
                f"-l{self.username}",
                f"-L1521:{self.tunnel_remote_host}:1521",
                "-oHostKeyAlgorithms=+ssh-rsa",
                "-oStrictHostKeyChecking=accept-new",
                "-oConnectTimeout=10",
                "-oServerAliveInterval=30",
                "-oServerAliveCountMax=3",
                "-N",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        stdout_stream = check.not_none(value=ssh_tunnel.stdout)

        while True:
            stdout = stdout_stream.readline()
            self.log.debug(msg=stdout)

            if stdout in [
                (
                    f"Warning: Permanently added '[{self.remote_host}]:"
                    f"{self.remote_port}' (RSA) to the list of known hosts.\r\n"
                ).encode(),
                b"A secure connection to your server has been established.\n",
            ]:
                continue
            elif stdout == b"To disconnect, simply close this window.\n":
                break
            else:
                ssh_tunnel.kill()
                raise SSHTunnelError(stdout)

        # Prevent a race condition with the ssh tunnel becoming fully established
        # before downstream code (e.g. PowerSchool ODBC) opens a forwarded port.
        time.sleep(1.0)

        return ssh_tunnel
