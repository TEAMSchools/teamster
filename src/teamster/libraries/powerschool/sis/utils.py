import subprocess

from sqlalchemy import text

from teamster.libraries.ssh.resources import SSHResource


def open_ssh_tunnel(ssh_resource: SSHResource):
    ssh_tunnel = subprocess.Popen(
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
            "-oConnectTimeout=10",
            "-N",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    while True:
        if ssh_tunnel.stdout is not None:
            stdout = ssh_tunnel.stdout.readline()
            ssh_resource.log.debug(msg=stdout)

            if stdout in [
                (
                    f"Warning: Permanently added '[{ssh_resource.remote_host}]:"
                    f"{ssh_resource.remote_port}' (RSA) to the list of known hosts.\r\n"
                ).encode(),
                b"A secure connection to your server has been established.\n",
            ]:
                continue
            elif stdout == b"To disconnect, simply close this window.\n":
                break
            else:
                ssh_tunnel.kill()
                raise Exception(stdout)

    return ssh_tunnel


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
