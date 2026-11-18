"""The folder asset stamps each row with its own file's mtime, only when asked."""

from unittest.mock import MagicMock

import pytest
from dagster import materialize, mem_io_manager
from paramiko import SFTPAttributes

from teamster.libraries.sftp.assets import build_sftp_folder_asset

AVRO_SCHEMA = {
    "type": "record",
    "name": "test",
    "fields": [
        {"name": "col", "type": ["null", "string"], "default": None},
        {
            "name": "source_file_modified_timestamp",
            "type": ["null", "long"],
            "default": None,
        },
    ],
}


def _attr(mtime: int) -> SFTPAttributes:
    attr = SFTPAttributes()
    attr.st_mtime = mtime
    return attr


def _records(tmp_path, add_source_file_modified_timestamp: bool) -> list[dict]:
    # one older and one newer file, as with an EOC file and a re-issued NJSLA
    # file that both carry the same test
    local_paths = {}

    for name, value in [("old", "a"), ("new", "b")]:
        local_path = tmp_path / f"{name}.csv"
        local_path.write_text(f"col\n{value}\n")
        local_paths[f"./{name}.csv"] = str(local_path)

    ssh = MagicMock()
    ssh.listdir_attr_r.return_value = [
        (_attr(100), "./old.csv"),
        (_attr(200), "./new.csv"),
    ]
    ssh.sftp_get.side_effect = lambda remote_filepath, **_: local_paths[remote_filepath]

    asset = build_sftp_folder_asset(
        asset_key=["test", "cambium", "njsla"],
        remote_dir_regex=r"\.",
        remote_file_regex=r"\w+\.csv",
        ssh_resource_key="ssh_test",
        avro_schema=AVRO_SCHEMA,
        add_source_file_modified_timestamp=add_source_file_modified_timestamp,
    )

    result = materialize(
        assets=[asset],
        resources={"ssh_test": ssh, "io_manager_gcs_avro": mem_io_manager},
    )

    records, _ = result.output_for_node("test__cambium__njsla")

    return records


def test_each_row_carries_its_own_files_mtime(tmp_path):
    records = _records(tmp_path, add_source_file_modified_timestamp=True)

    assert {(r["col"], r["source_file_modified_timestamp"]) for r in records} == {
        ("a", 100),
        ("b", 200),
    }


def test_rows_are_not_stamped_by_default(tmp_path):
    records = _records(tmp_path, add_source_file_modified_timestamp=False)

    assert all("source_file_modified_timestamp" not in r for r in records)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
