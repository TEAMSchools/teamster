from unittest.mock import MagicMock

from dagster import build_resources
from paramiko import SFTPAttributes

from teamster.libraries.ssh.resources import SSHResource


def _make_sftp_attr(
    filename: str, st_mode: int, st_mtime: int, st_size: int
) -> SFTPAttributes:
    attr = SFTPAttributes()
    attr.filename = filename
    attr.st_mode = st_mode
    attr.st_mtime = st_mtime
    attr.st_size = st_size
    return attr


# regular file mode
FILE_MODE = 0o100644
# directory mode
DIR_MODE = 0o40755


def _build_mock_sftp(dir_tree: dict) -> MagicMock:
    """Build a mock SFTPClient from a directory tree dict.

    Args:
        dir_tree: Nested dict where keys are dir paths and values are lists of
            SFTPAttributes. Use nested dicts for subdirectories.
    """
    sftp = MagicMock()

    def listdir_attr(path: str) -> list[SFTPAttributes]:
        return dir_tree.get(path, [])

    sftp.listdir_attr.side_effect = listdir_attr
    return sftp


def test_min_mtime_filters_old_files():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("old.csv", FILE_MODE, st_mtime=100, st_size=50),
                _make_sftp_attr("new.csv", FILE_MODE, st_mtime=300, st_size=50),
            ],
        }
    )

    with build_resources(
        {"ssh": SSHResource(remote_host="fake-host", username="u", password="p")}
    ) as resources:
        files = resources.ssh._inner_listdir_attr_r(
            sftp_client=sftp,
            remote_dir=".",
            exclude_dirs=[],
            min_mtime=200,
        )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["new.csv"]


def test_min_mtime_none_returns_all_files():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("old.csv", FILE_MODE, st_mtime=100, st_size=50),
                _make_sftp_attr("new.csv", FILE_MODE, st_mtime=300, st_size=50),
            ],
        }
    )

    with build_resources(
        {"ssh": SSHResource(remote_host="fake-host", username="u", password="p")}
    ) as resources:
        files = resources.ssh._inner_listdir_attr_r(
            sftp_client=sftp,
            remote_dir=".",
            exclude_dirs=[],
        )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["old.csv", "new.csv"]


def test_dir_mtimes_skips_unchanged_subtree():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("subdir", DIR_MODE, st_mtime=100, st_size=0),
            ],
            "subdir": [
                _make_sftp_attr("file.csv", FILE_MODE, st_mtime=150, st_size=50),
            ],
        }
    )

    with build_resources(
        {"ssh": SSHResource(remote_host="fake-host", username="u", password="p")}
    ) as resources:
        # dir_mtimes says subdir was last seen at mtime=100 — unchanged, skip it
        files, updated_dir_mtimes = resources.ssh._inner_listdir_attr_r(
            sftp_client=sftp,
            remote_dir=".",
            exclude_dirs=[],
            dir_mtimes={"subdir": 100},
        )

    assert files == []
    assert updated_dir_mtimes["subdir"] == 100
    # subdir should NOT have been listed
    sftp.listdir_attr.assert_called_once_with(".")


def test_dir_mtimes_traverses_changed_subtree():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("subdir", DIR_MODE, st_mtime=200, st_size=0),
            ],
            "subdir": [
                _make_sftp_attr("file.csv", FILE_MODE, st_mtime=250, st_size=50),
            ],
        }
    )

    with build_resources(
        {"ssh": SSHResource(remote_host="fake-host", username="u", password="p")}
    ) as resources:
        # dir_mtimes says subdir was last seen at mtime=100 — changed, traverse it
        files, updated_dir_mtimes = resources.ssh._inner_listdir_attr_r(
            sftp_client=sftp,
            remote_dir=".",
            exclude_dirs=[],
            dir_mtimes={"subdir": 100},
        )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["file.csv"]
    assert updated_dir_mtimes["subdir"] == 200


def test_dir_mtimes_traverses_unseen_directory():
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("newdir", DIR_MODE, st_mtime=300, st_size=0),
            ],
            "newdir": [
                _make_sftp_attr("data.csv", FILE_MODE, st_mtime=350, st_size=50),
            ],
        }
    )

    with build_resources(
        {"ssh": SSHResource(remote_host="fake-host", username="u", password="p")}
    ) as resources:
        # empty dir_mtimes — newdir is unseen, must traverse
        files, updated_dir_mtimes = resources.ssh._inner_listdir_attr_r(
            sftp_client=sftp,
            remote_dir=".",
            exclude_dirs=[],
            dir_mtimes={},
        )

    filenames = [attr.filename for attr, _ in files]
    assert filenames == ["data.csv"]
    assert updated_dir_mtimes["newdir"] == 300


def test_dir_mtimes_none_returns_list_only():
    """When dir_mtimes is None, return type is list (backward compat)."""
    sftp = _build_mock_sftp(
        {
            ".": [
                _make_sftp_attr("file.csv", FILE_MODE, st_mtime=100, st_size=50),
            ],
        }
    )

    with build_resources(
        {"ssh": SSHResource(remote_host="fake-host", username="u", password="p")}
    ) as resources:
        result = resources.ssh._inner_listdir_attr_r(
            sftp_client=sftp,
            remote_dir=".",
            exclude_dirs=[],
        )

    assert isinstance(result, list)
    assert len(result) == 1
