from collections.abc import Sequence
from unittest.mock import MagicMock

from dagster import AssetKey, RunRequest, SensorResult, build_sensor_context
from dagster_shared import check
from paramiko import SFTPAttributes

from teamster.code_locations.kippnewark.edplan.sensors import sftp_sensor

NJSMART_KEY = AssetKey(["kippnewark", "edplan", "njsmart_powerschool"])
SECTION_504_KEY = AssetKey(["kippnewark", "edplan", "section_504_student_report"])


def _run_sensor(filenames: list[str]) -> Sequence[RunRequest]:
    files = []
    for filename in filenames:
        attr = SFTPAttributes()
        attr.filename = filename
        attr.st_mtime = 1794500000
        attr.st_size = 100
        files.append((attr, f"Reports/{filename}"))

    ssh = MagicMock()
    ssh.listdir_attr_r_or_skip.return_value = files

    result = check.inst(
        sftp_sensor(
            context=build_sensor_context(sensor_name=sftp_sensor.name),
            ssh_edplan=ssh,
        ),
        SensorResult,
    )

    return check.not_none(result.run_requests)


def test_both_files_request_one_run_per_asset():
    run_requests = _run_sensor(
        ["NJSMART-PowerSchool.txt", "EDPlan-504StudentReport.csv"]
    )

    assert len(run_requests) == 2
    assert {tuple(r.asset_selection or []) for r in run_requests} == {
        (NJSMART_KEY,),
        (SECTION_504_KEY,),
    }
    assert len({r.run_key for r in run_requests}) == 2


def test_only_njsmart_file_requests_only_njsmart():
    run_requests = _run_sensor(["NJSMART-PowerSchool.txt"])

    assert len(run_requests) == 1
    assert run_requests[0].asset_selection == [NJSMART_KEY]
