import re

from dagster import EnvVar, build_resources

from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.core.utils.functions import regex_pattern_replace


def _test_resource(remote_filepath, remote_file_regex):
    with build_resources(
        resources={
            "ssh": SSHConfigurableResource(
                remote_host="kipptaf.couchdrop.io",
                username=EnvVar("COUCHDROP_SFTP_USERNAME"),
                password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
            )
        }
    ) as resources:
        ssh: SSHConfigurableResource = resources.ssh

    conn = ssh.get_connection()

    with conn.open_sftp() as sftp_client:
        ls = sftp_client.listdir_attr(path=remote_filepath)

    conn.close()

    file_matches = [
        f
        for f in ls
        if re.match(pattern=remote_file_regex, string=f.filename) is not None
    ]

    for f in file_matches:
        ssh.sftp_get(
            remote_filepath=f"{remote_filepath}/{f.filename}",
            local_filepath=f"./env/fldoe/{f.filename}",
        )


def test_fast():
    remote_filepath = (
        r"/teamster-kippmiami/couchdrop/fldoe/fast/(?P<school_year>\d+)/(?P<term>PM\d)"
    )

    remote_filepath_regex_composed = regex_pattern_replace(
        pattern=remote_filepath, replacements={"school_year": "2022", "term": "PM3"}
    )

    print(remote_filepath_regex_composed)

    _test_resource(
        remote_filepath=remote_filepath_regex_composed, remote_file_regex=r".*\.csv"
    )
