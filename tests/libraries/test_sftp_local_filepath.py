"""Unit tests for the SFTP asset local download path builder (no external deps)."""

import pytest

from teamster.libraries.sftp.assets import build_local_filepath

ASSET_KEY_STRING = "kipptaf/nsc/student_tracker"
LOCAL_DIR = f"/tmp/dagster/{ASSET_KEY_STRING}"


def test_relative_remote_path_keeps_directory_structure():
    assert (
        build_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath="reconcile_report_files/2026/report.csv",
        )
        == f"{LOCAL_DIR}/reconcile_report_files/2026/report.csv"
    )


def test_absolute_remote_path_nests_under_the_asset_directory():
    assert (
        build_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath="/data-team/kipptaf/nsc/student_tracker/report.csv",
        )
        == f"{LOCAL_DIR}/data-team/kipptaf/nsc/student_tracker/report.csv"
    )


def test_same_basename_in_different_remote_dirs_does_not_collide():
    first = build_local_filepath(
        asset_key_string=ASSET_KEY_STRING, remote_filepath="/BM/report.csv"
    )
    second = build_local_filepath(
        asset_key_string=ASSET_KEY_STRING, remote_filepath="/PM/report.csv"
    )

    assert first != second


def test_traversing_remote_path_is_rejected():
    with pytest.raises(ValueError, match="resolves outside"):
        build_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath=(
                "report.csv/../../../../../../app/.venv/lib/python3.13/"
                "site-packages/evil.pth"
            ),
        )


def test_sibling_directory_of_the_asset_directory_is_rejected():
    with pytest.raises(ValueError, match="resolves outside"):
        build_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath="../student_tracker_evil/report.csv",
        )
