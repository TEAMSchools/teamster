from unittest.mock import MagicMock

from dagster import SensorResult, build_sensor_context
from dagster_shared import check
from paramiko import SFTPAttributes

from teamster.code_locations.kipppaterson.edplan.sensors import sftp_sensor

FILENAME = "EDPlan Special Education Data Export.txt"


def test_late_evening_file_uses_local_date():
    """A file written at 23:30 ET is already the next day in UTC.

    The partitions are daily in America/New_York, so the key must be the
    Eastern date, or it names a partition that does not exist yet.
    """
    attr = SFTPAttributes()
    attr.filename = FILENAME
    attr.st_mtime = 1792294200  # 2026-10-17 23:30 EDT, 2026-10-18 03:30 UTC
    attr.st_size = 100

    ssh = MagicMock()
    ssh.listdir_attr_r_or_skip.return_value = [(attr, f"Reports/{FILENAME}")]

    result = check.inst(
        sftp_sensor(
            context=build_sensor_context(sensor_name=sftp_sensor.name),
            ssh_edplan=ssh,
        ),
        SensorResult,
    )

    assert [r.partition_key for r in check.not_none(result.run_requests)] == [
        "2026-10-17"
    ]
