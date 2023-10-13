import re

from dagster import EnvVar, build_resources
from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.core.utils.functions import regex_pattern_replace

SUBJECTS = ["ela", "math"]


def _test_resource(remote_filepath, remote_file_regex):
    with build_resources(
        resources={
            "ssh": SSHConfigurableResource(
                remote_host="prod-sftp-1.aws.cainc.com",
                username=EnvVar("IREADY_SFTP_USERNAME"),
                password=EnvVar("IREADY_SFTP_PASSWORD"),
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
            local_filepath=f"./env/iready/{f.filename}",
        )


def test_diagnostic_results():
    CODE_LOCATION = "nj-kipp_nj"

    for subject in SUBJECTS:
        remote_file_regex_composed = regex_pattern_replace(
            pattern=r"diagnostic_results_(?P<subject>).csv",
            replacements={"subject": subject},
        )

        _test_resource(
            remote_filepath=f"/exports/{CODE_LOCATION}/Current_Year",
            remote_file_regex=remote_file_regex_composed,
        )


def test_personalized_instruction_by_lesson():
    CODE_LOCATION = "nj-kipp_nj"

    for subject in SUBJECTS:
        remote_file_regex_composed = regex_pattern_replace(
            pattern=r"personalized_instruction_by_lesson_(?P<subject>).csv",
            replacements={"subject": subject},
        )

        _test_resource(
            remote_filepath=f"/exports/{CODE_LOCATION}/Current_Year",
            remote_file_regex=remote_file_regex_composed,
        )


def test_instructional_usage_data():
    CODE_LOCATION = "nj-kipp_nj"

    for subject in SUBJECTS:
        remote_file_regex_composed = regex_pattern_replace(
            pattern=r"instructional_usage_data_(?P<subject>).csv",
            replacements={"subject": subject},
        )

        _test_resource(
            remote_filepath=f"/exports/{CODE_LOCATION}/Current_Year",
            remote_file_regex=remote_file_regex_composed,
        )
