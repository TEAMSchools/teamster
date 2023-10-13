import pathlib
import re
from stat import S_ISDIR, S_ISREG

from dagster import EnvVar, build_resources
from paramiko import SFTPClient

from teamster.core.ssh.resources import SSHConfigurableResource


def listdir_attr_r(sftp_client: SFTPClient, remote_dir: str, files: list = []):
    for file in sftp_client.listdir_attr(remote_dir):
        filepath = str(pathlib.Path(remote_dir) / file.filename)

        if S_ISDIR(file.st_mode):
            listdir_attr_r(sftp_client=sftp_client, remote_dir=filepath, files=files)
        elif S_ISREG(file.st_mode):
            files.append(filepath)

    return files


def _test(ssh_configurable_resource, remote_file_regex_composed, remote_dir="."):
    with build_resources(resources={"ssh": ssh_configurable_resource}) as resources:
        ssh: SSHConfigurableResource = resources.ssh

    # list files remote filepath
    with ssh.get_connection() as conn:
        with conn.open_sftp() as sftp_client:
            files = listdir_attr_r(sftp_client=sftp_client, remote_dir=remote_dir)

    # find matching file for partition
    if remote_dir == ".":
        match_pattern = remote_file_regex_composed
    else:
        match_pattern = f"{remote_dir}/{remote_file_regex_composed}"

    file_matches = [
        f for f in files if re.match(pattern=match_pattern, string=f) is not None
    ]

    file_match = file_matches[0] if file_matches else None

    print(file_match)


def test_iready_nj():
    _test(
        ssh_configurable_resource=SSHConfigurableResource(
            remote_host="prod-sftp-1.aws.cainc.com",
            username=EnvVar("IREADY_SFTP_USERNAME"),
            password=EnvVar("IREADY_SFTP_PASSWORD"),
        ),
        remote_dir="/exports/nj-kipp_nj",
        remote_file_regex_composed=r"Current_Year/diagnostic_results_ela\.csv",
    )


def test_renlearn_miami():
    _test(
        ssh_configurable_resource=SSHConfigurableResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
        ),
        remote_file_regex_composed=r"KIPP Miami\.zip",
    )


def test_fldoe():
    _test(
        ssh_configurable_resource=SSHConfigurableResource(
            remote_host="kipptaf.couchdrop.io",
            username=EnvVar("COUCHDROP_SFTP_USERNAME"),
            password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
        ),
        remote_dir="/teamster-kippmiami/couchdrop/fldoe/fast",
        remote_file_regex_composed=r"2022/PM1/.*3\w*ELAReading.*\.csv",
    )
