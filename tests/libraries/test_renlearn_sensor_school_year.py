import zipfile
from unittest.mock import MagicMock

from teamster.libraries.renlearn.sensors import _school_year_start_date

STAR_HEADER = '"RenaissanceClientID","SchoolYear","StudentIdentifier"\n'
STAR_ROW = '"1234","2026-2027","5678"\n'


def _build_ssh(tmp_path, members: dict[str, str]) -> MagicMock:
    """Return a mock SSHResource whose sftp_get yields a zip of `members`."""
    archive_path = tmp_path / "archive.zip"

    with zipfile.ZipFile(archive_path, mode="w") as zip_file:
        for name, content in members.items():
            zip_file.writestr(name, content)

    ssh = MagicMock()
    ssh.sftp_get.return_value = str(archive_path)
    return ssh


def test_school_year_start_date_skips_empty_members(tmp_path):
    """An empty CSV is skipped; the first populated SchoolYear wins."""
    ssh = _build_ssh(
        tmp_path,
        {"SM.csv": "", "SR.csv": "", "AR.csv": STAR_HEADER + STAR_ROW},
    )

    assert (
        _school_year_start_date(ssh=ssh, remote_filepath="KIPP TEAM & Family.zip")
        == "2026-07-01"
    )


def test_school_year_start_date_returns_none_without_column(tmp_path):
    """No SchoolYear column means the caller must fall back."""
    ssh = _build_ssh(
        tmp_path,
        {"SM_Dashboard_Standards_v2.csv": '"StudentIdentifier"\n"5678"\n'},
    )

    assert _school_year_start_date(ssh=ssh, remote_filepath="KIPP Miami.zip") is None


def test_school_year_start_date_returns_none_when_blank(tmp_path):
    """A present-but-empty SchoolYear is not a usable partition key."""
    ssh = _build_ssh(tmp_path, {"SM.csv": STAR_HEADER + '"1234","","5678"\n'})

    assert _school_year_start_date(ssh=ssh, remote_filepath="KIPP Miami.zip") is None


def _build_ssh_for_sensor(tmp_path, filename: str, members: dict[str, str]):
    """Mock SSHResource that lists one archive and serves its contents."""
    from paramiko import SFTPAttributes

    ssh = _build_ssh(tmp_path, members)

    attr = SFTPAttributes()
    attr.filename = filename
    attr.st_mtime = 1788238507
    attr.st_size = 5696

    ssh.listdir_attr_r_or_skip.return_value = [(attr, filename)]
    return ssh


def test_sensor_requests_partition_from_school_year(tmp_path):
    """The run request lands in the fiscal year the archive itself names."""
    from dagster import build_sensor_context

    from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
    from teamster.code_locations.kippmiami.renlearn import assets
    from teamster.libraries.renlearn.sensors import build_renlearn_sftp_sensor

    ssh = _build_ssh_for_sensor(
        tmp_path,
        filename="KIPP Miami.zip",
        # a wall-clock partition key would stamp the CURRENT fiscal year
        members={"SM.csv": STAR_HEADER + '"1234","2025-2026","5678"\n'},
    )

    sftp_sensor = build_renlearn_sftp_sensor(
        code_location=CODE_LOCATION,
        asset_selection=assets,
        partition_key_start_date="2026-07-01",
        timezone=LOCAL_TIMEZONE,
    )

    result = sftp_sensor(
        build_sensor_context(resources={"ssh_renlearn": ssh})  # type: ignore[arg-type]
    )

    partition_keys = {
        run_request.partition_key for run_request in result.run_requests or []
    }

    assert partition_keys
    assert all(
        check_key is not None and check_key.startswith("2025-07-01")
        for check_key in partition_keys
    )
