"""Unit tests for the SFTP asset local download path builder (no external deps)."""

import pytest

from teamster.libraries.sftp.assets import resolve_local_filepath

ASSET_KEY_STRING = "kipptaf/nsc/student_tracker"
LOCAL_DIR = f"/tmp/dagster/{ASSET_KEY_STRING}"


def test_relative_remote_path_keeps_directory_structure():
    assert (
        resolve_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath="reconcile_report_files/2026/report.csv",
        )
        == f"{LOCAL_DIR}/reconcile_report_files/2026/report.csv"
    )


def test_absolute_remote_path_nests_under_the_asset_directory():
    assert (
        resolve_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath="/data-team/kipptaf/nsc/student_tracker/report.csv",
        )
        == f"{LOCAL_DIR}/data-team/kipptaf/nsc/student_tracker/report.csv"
    )


def test_same_basename_in_different_remote_dirs_does_not_collide():
    first = resolve_local_filepath(
        asset_key_string=ASSET_KEY_STRING, remote_filepath="/BM/report.csv"
    )
    second = resolve_local_filepath(
        asset_key_string=ASSET_KEY_STRING, remote_filepath="/PM/report.csv"
    )

    assert first != second


def test_traversing_remote_path_is_rejected():
    with pytest.raises(ValueError, match="resolves outside"):
        resolve_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath=(
                "report.csv/../../../../../../app/.venv/lib/python3.13/"
                "site-packages/evil.pth"
            ),
        )


def test_sibling_directory_of_the_asset_directory_is_rejected():
    with pytest.raises(ValueError, match="resolves outside"):
        resolve_local_filepath(
            asset_key_string=ASSET_KEY_STRING,
            remote_filepath="../student_tracker_evil/report.csv",
        )


@pytest.mark.parametrize(
    "remote_filepath,expected_suffix",
    [
        # `remote_dir_regex` values actually deployed today (see
        # `grep -rh "remote_dir_regex=" src/teamster/code_locations/`). Pins
        # the on-disk path so a future normalisation change can't silently
        # relocate a real asset's downloads.
        ("/report.csv", "/report.csv"),
        ("/BM/report.csv", "/BM/report.csv"),
        (
            "/data-team/kipptaf/nsc/student_tracker/report.csv",
            "/data-team/kipptaf/nsc/student_tracker/report.csv",
        ),
        ("Reports/report.csv", "/Reports/report.csv"),
    ],
)
def test_deployed_remote_dir_values_produce_a_stable_local_path(
    remote_filepath, expected_suffix
):
    assert (
        resolve_local_filepath(
            asset_key_string=ASSET_KEY_STRING, remote_filepath=remote_filepath
        )
        == f"{LOCAL_DIR}{expected_suffix}"
    )
