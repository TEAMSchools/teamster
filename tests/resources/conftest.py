"""Per-server SSHResource fixtures for SFTP integration tests.

Authentication is handled by the root ``tests/conftest.py`` session-scoped
fixture that bootstraps 1Password secrets into ``os.environ`` on first run.
Individual fixtures here skip when their required environment variables are
unset (e.g. CI without 1Password access).
"""

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from dagster import EnvVar
from dagster_shared import check

from teamster.libraries.ssh.resources import SSHResource


@dataclass(frozen=True)
class SFTPServer:
    name: str
    env_vars: tuple[str, ...]
    builder: Callable[[], SSHResource]
    remote_dir: str
    exclude_dirs: tuple[str, ...] = ()


def _password_ssh(
    *,
    host_env: str,
    user_env: str,
    pass_env: str,
    port: int = 22,
    port_env: str | None = None,
    timeout: int | None = None,
    enable_legacy_rsa: bool = False,
) -> Callable[[], SSHResource]:
    def build() -> SSHResource:
        resolved_port = port
        if port_env is not None:
            resolved_port = int(check.not_none(value=EnvVar(port_env).get_value()))
        kwargs: dict = {
            "remote_host": EnvVar(host_env),
            "remote_port": resolved_port,
            "username": EnvVar(user_env),
            "password": EnvVar(pass_env),
            "test": True,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout
        if enable_legacy_rsa:
            kwargs["enable_legacy_rsa"] = enable_legacy_rsa
        return SSHResource(**kwargs)

    return build


def _egencia() -> SSHResource:
    return SSHResource(
        remote_host=EnvVar("EGENCIA_SFTP_HOST"),
        remote_port=22,
        username=EnvVar("EGENCIA_SFTP_USERNAME"),
        key_file="/etc/secret-volume/id_rsa_egencia",
        test=True,
    )


SFTP_SERVERS: tuple[SFTPServer, ...] = (
    SFTPServer(
        name="amplify",
        env_vars=(
            "AMPLIFY_SFTP_HOST",
            "AMPLIFY_SFTP_USERNAME",
            "AMPLIFY_SFTP_PASSWORD",
        ),
        builder=_password_ssh(
            host_env="AMPLIFY_SFTP_HOST",
            user_env="AMPLIFY_SFTP_USERNAME",
            pass_env="AMPLIFY_SFTP_PASSWORD",
        ),
        remote_dir="/",
    ),
    SFTPServer(
        name="adp_workforce_now",
        env_vars=("ADP_SFTP_HOST_IP", "ADP_SFTP_USERNAME", "ADP_SFTP_PASSWORD"),
        builder=_password_ssh(
            host_env="ADP_SFTP_HOST_IP",
            user_env="ADP_SFTP_USERNAME",
            pass_env="ADP_SFTP_PASSWORD",
        ),
        remote_dir=".",
        exclude_dirs=("./payroll",),
    ),
    SFTPServer(
        name="clever",
        env_vars=("CLEVER_SFTP_HOST", "CLEVER_SFTP_USERNAME", "CLEVER_SFTP_PASSWORD"),
        builder=_password_ssh(
            host_env="CLEVER_SFTP_HOST",
            user_env="CLEVER_SFTP_USERNAME",
            pass_env="CLEVER_SFTP_PASSWORD",
            timeout=30,
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="couchdrop",
        env_vars=(
            "COUCHDROP_SFTP_HOST",
            "COUCHDROP_SFTP_USERNAME",
            "COUCHDROP_SFTP_PASSWORD",
        ),
        builder=_password_ssh(
            host_env="COUCHDROP_SFTP_HOST",
            user_env="COUCHDROP_SFTP_USERNAME",
            pass_env="COUCHDROP_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="coupa",
        env_vars=("COUPA_SFTP_HOST", "COUPA_SFTP_USERNAME", "COUPA_SFTP_PASSWORD"),
        builder=_password_ssh(
            host_env="COUPA_SFTP_HOST",
            user_env="COUPA_SFTP_USERNAME",
            pass_env="COUPA_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="deanslist",
        env_vars=(
            "DEANSLIST_SFTP_HOST",
            "DEANSLIST_SFTP_USERNAME",
            "DEANSLIST_SFTP_PASSWORD",
        ),
        builder=_password_ssh(
            host_env="DEANSLIST_SFTP_HOST",
            user_env="DEANSLIST_SFTP_USERNAME",
            pass_env="DEANSLIST_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="edplan",
        env_vars=("EDPLAN_SFTP_HOST", "EDPLAN_SFTP_USERNAME", "EDPLAN_SFTP_PASSWORD"),
        builder=_password_ssh(
            host_env="EDPLAN_SFTP_HOST",
            user_env="EDPLAN_SFTP_USERNAME",
            pass_env="EDPLAN_SFTP_PASSWORD",
            timeout=30,
            enable_legacy_rsa=True,
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="egencia",
        env_vars=("EGENCIA_SFTP_HOST", "EGENCIA_SFTP_USERNAME"),
        builder=_egencia,
        remote_dir=".",
    ),
    SFTPServer(
        name="idauto",
        env_vars=("KTAF_SFTP_HOST_IP", "KTAF_SFTP_USERNAME", "KTAF_SFTP_PASSWORD"),
        builder=_password_ssh(
            host_env="KTAF_SFTP_HOST_IP",
            user_env="KTAF_SFTP_USERNAME",
            pass_env="KTAF_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="illuminate",
        env_vars=(
            "ILLUMINATE_SFTP_HOST",
            "ILLUMINATE_SFTP_USERNAME",
            "ILLUMINATE_SFTP_PASSWORD",
        ),
        builder=_password_ssh(
            host_env="ILLUMINATE_SFTP_HOST",
            user_env="ILLUMINATE_SFTP_USERNAME",
            pass_env="ILLUMINATE_SFTP_PASSWORD",
            timeout=30,
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="iready",
        env_vars=("IREADY_SFTP_HOST", "IREADY_SFTP_USERNAME", "IREADY_SFTP_PASSWORD"),
        builder=_password_ssh(
            host_env="IREADY_SFTP_HOST",
            user_env="IREADY_SFTP_USERNAME",
            pass_env="IREADY_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="lattice",
        env_vars=(
            "LATTICE_SFTP_HOST",
            "LATTICE_SFTP_USERNAME",
            "LATTICE_SFTP_PASSWORD",
        ),
        builder=_password_ssh(
            host_env="LATTICE_SFTP_HOST",
            user_env="LATTICE_SFTP_USERNAME",
            pass_env="LATTICE_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="littlesis",
        env_vars=(
            "LITTLESIS_SFTP_HOST",
            "LITTLESIS_SFTP_PORT",
            "LITTLESIS_SFTP_USERNAME",
            "LITTLESIS_SFTP_PASSWORD",
        ),
        builder=_password_ssh(
            host_env="LITTLESIS_SFTP_HOST",
            user_env="LITTLESIS_SFTP_USERNAME",
            pass_env="LITTLESIS_SFTP_PASSWORD",
            port_env="LITTLESIS_SFTP_PORT",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="renlearn",
        env_vars=(
            "RENLEARN_SFTP_HOST",
            "RENLEARN_SFTP_USERNAME",
            "RENLEARN_SFTP_PASSWORD",
        ),
        builder=_password_ssh(
            host_env="RENLEARN_SFTP_HOST",
            user_env="RENLEARN_SFTP_USERNAME",
            pass_env="RENLEARN_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
    SFTPServer(
        name="titan",
        env_vars=("TITAN_SFTP_HOST", "TITAN_SFTP_USERNAME", "TITAN_SFTP_PASSWORD"),
        builder=_password_ssh(
            host_env="TITAN_SFTP_HOST",
            user_env="TITAN_SFTP_USERNAME",
            pass_env="TITAN_SFTP_PASSWORD",
        ),
        remote_dir=".",
    ),
)


@pytest.fixture(params=SFTP_SERVERS, ids=lambda s: s.name)
def sftp_server(request: pytest.FixtureRequest) -> SFTPServer:
    server: SFTPServer = request.param
    missing = [name for name in server.env_vars if EnvVar(name).get_value() is None]
    if missing:
        pytest.skip(f"missing environment variables: {', '.join(missing)}")
    return server
