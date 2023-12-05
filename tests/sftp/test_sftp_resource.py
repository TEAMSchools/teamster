from dagster import EnvVar, build_asset_context, build_resources

from teamster.core.sftp.assets import match_sftp_files
from teamster.core.ssh.resources import SSHResource


def _test(ssh_configurable_resource, remote_file_regex_composed, remote_dir="."):
    context = build_asset_context()

    with build_resources(resources={"ssh": ssh_configurable_resource}) as resources:
        ssh: SSHResource = resources.ssh

    # find matching file for partition
    file_matches = match_sftp_files(
        ssh=ssh, remote_dir=remote_dir, remote_file_regex=remote_file_regex_composed
    )

    # exit if no matches
    if not file_matches:
        raise Exception(f"Found no files matching: {remote_file_regex_composed}")

    # download file from sftp
    if len(file_matches) > 1:
        context.log.warning(
            (
                f"Found multiple files matching: {remote_file_regex_composed}\n"
                f"{file_matches}"
            )
        )
        file_match = file_matches[0]
    else:
        file_match = file_matches[0]

    context.log.info(file_match)

    ssh.sftp_get(remote_filepath=file_match, local_filepath=f"./env/{file_match}")


def test_iready_nj():
    _test(
        ssh_configurable_resource=SSHResource(
            remote_host="prod-sftp-1.aws.cainc.com",
            username=EnvVar("IREADY_SFTP_USERNAME"),
            password=EnvVar("IREADY_SFTP_PASSWORD"),
        ),
        remote_dir="/exports/nj-kipp_nj",
        remote_file_regex_composed="Current_Year/diagnostic_results_ela.csv",
    )


def test_renlearn_miami():
    _test(
        ssh_configurable_resource=SSHResource(
            remote_host="sftp.renaissance.com",
            username=EnvVar("KIPPMIAMI_RENLEARN_SFTP_USERNAME"),
            password=EnvVar("KIPPMIAMI_RENLEARN_SFTP_PASSWORD"),
        ),
        remote_file_regex_composed="KIPP Miami.zip",
    )


def test_fldoe():
    # _test(
    #     ssh_configurable_resource=SSHResource(
    #         remote_host="kipptaf.couchdrop.io",
    #         username=EnvVar("COUCHDROP_SFTP_USERNAME"),
    #         password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
    #     ),
    #     remote_dir="/teamster-kippmiami/couchdrop/fldoe/fast",
    #     remote_file_regex_composed="2022/PM1/.*3\w*ELAReading.*\.csv",
    # )

    filenames = [
        "FSA_21SPR_132332_SRS-E_MATH_SCHL.csv",
        "FSA_21SPR_132332_SRS-E_ELA_GR04_10_SCHL.csv",
        "FSA_21SPR_132332_SRS-E_ELA_GR03_SCHL.csv",
        "FSA_21SPR_132332_SRS-E_SCI_SCHL.csv",
        "FSA_22SPR_132332_SRS-E_ELA_GR03_SCHL.csv",
        "FSA_22SPR_132332_SRS-E_SCI_SCHL.csv",
        "FSA_22SPR_132332_SRS-E_MATH_SCHL.csv",
        "FSA_22SPR_132332_SRS-E_ELA_GR04_10_SCHL.csv",
    ]

    for filename in filenames:
        _test(
            ssh_configurable_resource=SSHResource(
                remote_host="kipptaf.couchdrop.io",
                username=EnvVar("COUCHDROP_SFTP_USERNAME"),
                password=EnvVar("COUCHDROP_SFTP_PASSWORD"),
            ),
            remote_dir="/teamster-kippmiami/couchdrop/fldoe/fsa/student_scores",
            remote_file_regex_composed=filename,
        )
