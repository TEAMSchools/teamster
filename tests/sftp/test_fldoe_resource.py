import re

from dagster import EnvVar, build_resources
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.core.utils.functions import regex_pattern_replace

GRADE_LEVEL_SUBJECT = [
    "3\w*ELAReading",
    "3\w*Mathematics",
    "4\w*ELAReading",
    "4\w*Mathematics",
    "5\w*ELAReading",
    "5\w*Mathematics",
    "6\w*ELAReading",
    "6\w*Mathematics",
    "7\w*ELAReading",
    "7\w*Mathematics",
    "8\w*ELAReading",
    "8\w*Mathematics",
]


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
    for grade_level_subject in GRADE_LEVEL_SUBJECT:
        partition_keys = {
            "school_year_term": "2023/PM1",
            "grade_level_subject": grade_level_subject,
        }

        remote_filepath_regex_composed = regex_pattern_replace(
            pattern=r"/teamster-kippmiami/couchdrop/fldoe/fast/(?P<school_year_term>)",
            replacements=partition_keys,
        )

        remote_file_regex_composed = regex_pattern_replace(
            pattern=r".*(?P<grade_level_subject>).*\.csv", replacements=partition_keys
        )

        _test_resource(
            remote_filepath=remote_filepath_regex_composed,
            remote_file_regex=remote_file_regex_composed,
        )
