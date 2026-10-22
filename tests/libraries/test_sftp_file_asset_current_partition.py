from unittest.mock import MagicMock

from dagster import instance_for_test, materialize, mem_io_manager
from dagster_shared import check

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.sftp.assets import build_sftp_file_asset

PARTITIONS_DEF = FiscalYearPartitionsDefinition(
    start_date="2020-07-01", timezone="America/New_York", start_month=7
)


def test_past_partition_is_refused_before_any_sftp_call():
    """A past fiscal year holds its frozen pre-rollover snapshot.

    Re-running it would download today's file and overwrite that snapshot.
    """
    asset = build_sftp_file_asset(
        asset_key=["test", "sftp", "current_only"],
        remote_dir_regex="/exports",
        remote_file_regex=r"a\.csv",
        ssh_resource_key="ssh_test",
        avro_schema={},
        partitions_def=PARTITIONS_DEF,
        current_partition_only=True,
    )

    ssh = MagicMock()
    past_key = PARTITIONS_DEF.get_partition_keys()[0]

    with instance_for_test() as instance:
        result = materialize(
            assets=[asset],
            partition_key=past_key,
            resources={"ssh_test": ssh, "io_manager_gcs_avro": mem_io_manager},
            instance=instance,
            raise_on_error=False,
        )

    assert not result.success

    failure = result.get_step_failure_events()[0]
    # dagster wraps user code errors; the raised error is the cause
    error = check.not_none(check.not_none(failure.step_failure_data.error).cause)

    assert error.cls_name == "ValueError"
    assert past_key in error.message
    ssh.get_connection.assert_not_called()
    ssh.listdir_attr_r.assert_not_called()
    ssh.sftp_get.assert_not_called()
