import zipfile

from dagster import EnvVar, build_resources

from teamster.core.ssh.resources import SSHConfigurableResource
from teamster.core.utils.functions import regex_pattern_replace

MEMBER_FILES = [
    "AR.csv",
    "FL_FAST_SEL_Domains_K-2.csv",
    "FL_FAST_SEL_K-2.csv",
    "FL_FAST_SM_K-2.csv",
    "FL_FAST_SR_K-2.csv",
    "SEL_Dashboard_Standards_v2.csv",
    "SEL_SkillArea_v1.csv",
    "SEL.csv",
    "SM_Dashboard_Standards_v2.csv",
    "SM_SkillArea_v1.csv",
    "SM.csv",
    "SR_Dashboard_Standards_v2.csv",
    "SR_SkillArea_v1.csv",
    "SR.csv",
]


def test_regex_pattern_replace():
    regex_pattern_replace(None, replacements={})


def _test(code_location, remote_filepath, members):
    with build_resources(
        resources={
            "ssh": SSHConfigurableResource(
                remote_host="sftp.renaissance.com",
                username=EnvVar(f"{code_location}_RENLEARN_SFTP_USERNAME"),
                password=EnvVar(f"{code_location}_RENLEARN_SFTP_PASSWORD"),
            )
        },
    ) as resources:
        ssh: SSHConfigurableResource = resources.ssh

    local_filepath = ssh.sftp_get(
        remote_filepath=remote_filepath,
        local_filepath=f"./env/renlearn/{remote_filepath}",
    )

    if members is not None:
        with zipfile.ZipFile(file=local_filepath) as zf:
            for member in members:
                try:
                    zf.extract(member=member, path=f"./env/renlearn/{code_location}")
                except Exception:
                    continue


def test_kippmiami():
    _test(
        code_location="KIPPMIAMI",
        remote_filepath="KIPP Miami.zip",
        members=MEMBER_FILES,
    )


def test_kippnj():
    _test(
        code_location="KIPPNJ",
        remote_filepath="KIPP TEAM & Family.zip",
        members=MEMBER_FILES,
    )
