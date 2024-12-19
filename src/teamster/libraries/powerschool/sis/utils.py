import subprocess

from sqlalchemy import text

from teamster.libraries.ssh.resources import SSHResource


def open_ssh_tunnel(ssh_resource: SSHResource):
    return subprocess.Popen(
        args=[
            "sshpass",
            "-f/etc/secret-volume/powerschool_ssh_password.txt",
            "ssh",
            ssh_resource.remote_host,
            f"-p{ssh_resource.remote_port}",
            f"-l{ssh_resource.username}",
            f"-L1521:{ssh_resource.tunnel_remote_host}:1521",
            "-oHostKeyAlgorithms=+ssh-rsa",
            "-oStrictHostKeyChecking=accept-new",
            "-N",
        ],
    )


def get_query_text(
    table: str,
    column: str | None,
    start_value: str | None = None,
    end_value: str | None = None,
):
    # TODO: paramterize sqlalchemy query to resolve bandit/B608
    if column is None:
        query = f"SELECT COUNT(*) FROM {table}"
    elif end_value is None:
        query = (
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} >= "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )
    else:
        query = (
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {column} BETWEEN "
            f"TO_TIMESTAMP('{start_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6') AND "
            f"TO_TIMESTAMP('{end_value}', 'YYYY-MM-DD\"T\"HH24:MI:SS.FF6')"
        )

    return text(query)
