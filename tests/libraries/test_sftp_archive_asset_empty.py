"""An absent source must fail; a genuinely empty one must yield zero records."""

import zipfile
from unittest.mock import MagicMock

import pytest
from dagster import materialize, mem_io_manager
from paramiko import SFTPAttributes

from teamster.libraries.sftp.assets import build_sftp_archive_asset

AVRO_SCHEMA = {
    "type": "record",
    "name": "test",
    "fields": [{"name": "col", "type": ["null", "string"], "default": None}],
}


def _build_asset():
    return build_sftp_archive_asset(
        asset_key=["test", "renlearn", "star"],
        remote_dir_regex=r"\.",
        remote_file_regex=r"test\.zip",
        archive_file_regex=r"data\.csv",
        ssh_resource_key="ssh_test",
        avro_schema=AVRO_SCHEMA,
        slugify_cols=False,
    )


def _build_ssh(listing: list, archive_path: str | None = None) -> MagicMock:
    ssh = MagicMock()
    ssh.listdir_attr_r.return_value = listing

    if archive_path is not None:
        ssh.sftp_get.return_value = archive_path

    return ssh


def _listing(size: int) -> list:
    attr = SFTPAttributes()
    attr.filename = "test.zip"
    attr.st_mtime = 1788238507
    attr.st_size = size
    return [(attr, "./test.zip")]


def _materialize(ssh: MagicMock):
    return materialize(
        assets=[_build_asset()],
        resources={"ssh_test": ssh, "io_manager_gcs_avro": mem_io_manager},
        raise_on_error=False,
    )


def _failure_message(result) -> str:
    """Flatten every step failure's error chain -- the cause holds the raise."""
    messages = []

    for event in result.all_events:
        if event.event_type_value != "STEP_FAILURE":
            continue

        error = event.event_specific_data.error  # type: ignore[union-attr]

        while error is not None:
            messages.append(error.message)
            error = error.cause

    return " ".join(messages)


def test_missing_file_fails_instead_of_emptying_the_partition():
    """No match on the SFTP must not overwrite the partition with nothing."""
    result = _materialize(_build_ssh(listing=[]))

    assert not result.success
    assert "Found no files matching" in _failure_message(result)


def test_empty_archive_fails():
    """A 0-byte archive cannot be a readable zip."""
    result = _materialize(_build_ssh(listing=_listing(0), archive_path="/dev/null"))

    assert not result.success
    assert "Archive is empty" in _failure_message(result)


def test_empty_member_yields_zero_records(tmp_path):
    """A 0-byte member is real data -- renlearn ships empty SM.csv / SR.csv."""
    archive_path = tmp_path / "test.zip"

    with zipfile.ZipFile(archive_path, mode="w") as zip_file:
        zip_file.writestr("data.csv", "")

    result = _materialize(
        _build_ssh(listing=_listing(4096), archive_path=str(archive_path))
    )

    assert result.success

    # the records themselves, not just the count -- the old code reported 0
    # records while still writing one all-null row
    records, _ = result.output_for_node("test__renlearn__star")

    assert records == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
