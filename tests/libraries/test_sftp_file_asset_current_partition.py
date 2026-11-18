import os
import time
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from dagster import instance_for_test, materialize, mem_io_manager
from dagster_shared import check

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_file_asset

PARTITIONS_DEF = FiscalYearPartitionsDefinition(
    start_date="2020-07-01", timezone="America/New_York", start_month=7
)

AVRO_SCHEMA = {
    "type": "record",
    "name": "a",
    "fields": [
        {"name": "a", "type": ["null", "string"], "default": None},
        {"name": "source_file_name", "type": ["null", "string"], "default": None},
    ],
}


def _materialize(partition_key: str, file_mtime: float):
    asset = build_sftp_file_asset(
        asset_key=["test", "sftp", "current_only"],
        remote_dir_regex="/exports",
        remote_file_regex=r"a\.csv",
        ssh_resource_key="ssh_test",
        avro_schema=AVRO_SCHEMA,
        partitions_def=PARTITIONS_DEF,
        current_partition_only=True,
    )

    def sftp_get(remote_filepath: str, local_filepath: str) -> str:
        os.makedirs(os.path.dirname(local_filepath), exist_ok=True)
        with open(local_filepath, "w") as f:
            f.write("a\nx\n")
        return local_filepath

    ssh = MagicMock()
    ssh.listdir_attr_r.return_value = [
        (SimpleNamespace(st_mtime=file_mtime), "/exports/a.csv")
    ]
    ssh.sftp_get.side_effect = sftp_get

    with instance_for_test() as instance:
        result = materialize(
            assets=[asset],
            partition_key=partition_key,
            resources={"ssh_test": ssh, "io_manager_gcs_avro": mem_io_manager},
            instance=instance,
            raise_on_error=False,
        )

    return result, ssh


def test_past_partition_is_refused_before_download():
    """A past fiscal year holds its frozen pre-rollover snapshot.

    Re-running it would download today's file and overwrite that snapshot.
    """
    past_key = PARTITIONS_DEF.get_partition_keys()[0]

    result, ssh = _materialize(partition_key=past_key, file_mtime=time.time())

    assert not result.success

    failure = result.get_step_failure_events()[0]
    # dagster wraps user code errors; the raised error is the cause
    error = check.not_none(check.not_none(failure.step_failure_data.error).cause)

    assert error.cls_name == "ValueError"
    assert past_key in error.message
    ssh.sftp_get.assert_not_called()


def test_june_30_file_loads_into_its_fiscal_year_after_midnight():
    """The sensor sends a 23:59 June 30 file to the old year; the run starts later."""
    june_30 = datetime(2025, 6, 30, 23, 59, tzinfo=ZoneInfo("America/New_York"))

    result, ssh = _materialize(
        partition_key="2024-07-01", file_mtime=june_30.timestamp()
    )

    assert result.success
    ssh.sftp_get.assert_called_once()
