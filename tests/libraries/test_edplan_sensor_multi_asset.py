import json
from collections.abc import Sequence
from unittest.mock import MagicMock

from dagster import AssetKey, RunRequest, SensorResult, build_sensor_context
from dagster_shared import check
from paramiko import SFTPAttributes

from teamster.code_locations.kippnewark.edplan.sensors import sftp_sensor

NJSMART_KEY = AssetKey(["kippnewark", "edplan", "njsmart_powerschool"])
SECTION_504_KEY = AssetKey(["kippnewark", "edplan", "section_504_student_report"])


def _run_sensor(
    filenames: list[str], sensor=sftp_sensor, cursor: str | None = None
) -> Sequence[RunRequest]:
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
        sensor(
            context=build_sensor_context(sensor_name=sensor.name, cursor=cursor),
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

    by_key = {r.asset_selection[0]: r for r in run_requests if r.asset_selection}
    assert by_key[NJSMART_KEY].partition_key is not None
    assert by_key[SECTION_504_KEY].partition_key is None


def test_paterson_export_requests_its_njsmart_asset():
    from teamster.code_locations.kipppaterson.edplan.sensors import (
        sftp_sensor as paterson_sensor,
    )

    run_requests = _run_sensor(
        ["EDPlan Special Education Data Export.txt", "NJSMART-PowerSchool.txt"],
        sensor=paterson_sensor,
    )

    assert len(run_requests) == 1
    assert run_requests[0].asset_selection == [
        AssetKey(["kipppaterson", "edplan", "njsmart_powerschool"])
    ]


def test_one_asset_cursor_does_not_suppress_the_other():
    cursor = json.dumps({NJSMART_KEY.to_python_identifier(): 9e9})

    run_requests = _run_sensor(
        ["NJSMART-PowerSchool.txt", "EDPlan-504StudentReport.csv"], cursor=cursor
    )

    assert len(run_requests) == 1
    assert run_requests[0].asset_selection == [SECTION_504_KEY]


def test_only_njsmart_file_requests_only_njsmart():
    run_requests = _run_sensor(["NJSMART-PowerSchool.txt"])

    assert len(run_requests) == 1
    assert run_requests[0].asset_selection == [NJSMART_KEY]
