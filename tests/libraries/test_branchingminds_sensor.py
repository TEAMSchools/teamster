import json
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from dagster import SensorResult, SkipReason, build_sensor_context
from dagster_shared import check
from paramiko import SFTPAttributes

from teamster.core.utils.classes import FiscalYearPartitionsDefinition
from teamster.libraries.branchingminds.sensors import build_branchingminds_sftp_sensor
from teamster.libraries.sftp.assets import build_sftp_file_asset

TZ = ZoneInfo("America/New_York")

PARTITIONS_DEF = FiscalYearPartitionsDefinition(
    start_date="2024-07-01", timezone=str(TZ), start_month=7
)


def _asset(name: str):
    return build_sftp_file_asset(
        asset_key=["test", "branchingminds", name],
        remote_dir_regex="/exports",
        remote_file_regex=rf"{name}\.csv",
        ssh_resource_key="ssh_branchingminds",
        avro_schema={},
        partitions_def=PARTITIONS_DEF,
    )


ASSET_A = _asset("a")
ASSET_B = _asset("b")
A_ID = ASSET_A.key.to_python_identifier()
B_ID = ASSET_B.key.to_python_identifier()

SENSOR = build_branchingminds_sftp_sensor(
    code_location="test",
    timezone=TZ,
    asset_selection=[ASSET_A, ASSET_B],
    remote_dir="/exports",
)


def _ts(*args) -> float:
    return datetime(*args, tzinfo=TZ).timestamp()


def _file(name: str, mtime: float, size: int = 100):
    attr = SFTPAttributes()
    attr.filename = name
    attr.st_mtime = int(mtime)
    attr.st_size = size

    return (attr, f"/exports/{name}")


def _run(files, cursor: dict | None = None):
    ssh = MagicMock()
    ssh.listdir_attr_r_or_skip.return_value = files

    context = build_sensor_context(
        sensor_name=SENSOR.name, cursor=json.dumps(cursor) if cursor else None
    )

    return SENSOR(context=context, ssh_branchingminds=ssh)


def _result(files, cursor: dict | None = None) -> SensorResult:
    return check.inst(_run(files, cursor), SensorResult)


def test_june_30_late_evening_is_prior_fiscal_year():
    result = _result([_file("a.csv", _ts(2025, 6, 30, 23, 59))])

    assert [r.partition_key for r in check.not_none(result.run_requests)] == [
        "2024-07-01"
    ]


def test_july_1_early_morning_is_new_fiscal_year():
    result = _result([_file("a.csv", _ts(2025, 7, 1, 0, 30))])

    assert [r.partition_key for r in check.not_none(result.run_requests)] == [
        "2025-07-01"
    ]


def test_cursor_is_per_asset_max_mtime():
    t = int(_ts(2026, 10, 1, 12, 0))

    result = _result(
        [_file("a.csv", t + 150), _file("b.csv", t + 150)],
        cursor={A_ID: t + 200, B_ID: t + 100},
    )

    run_requests = check.not_none(result.run_requests)

    assert len(run_requests) == 1
    assert run_requests[0].asset_selection == [ASSET_B.key]
    assert json.loads(check.not_none(result.cursor)) == {
        A_ID: t + 200,
        B_ID: t + 150,
    }


def test_empty_file_is_skipped():
    t = int(_ts(2026, 10, 1, 12, 0))

    result = _result([_file("a.csv", t, size=0)], cursor={A_ID: t - 1})

    assert not result.run_requests
    assert json.loads(check.not_none(result.cursor)) == {A_ID: t - 1}


def test_changed_assets_share_one_run():
    t = _ts(2026, 10, 1, 12, 0)

    result = _result([_file("a.csv", t), _file("b.csv", t + 60)])

    run_requests = check.not_none(result.run_requests)

    assert len(run_requests) == 1
    assert set(check.not_none(run_requests[0].asset_selection)) == {
        ASSET_A.key,
        ASSET_B.key,
    }


def test_skip_reason_passes_through():
    skip = SkipReason("SFTP unreachable")

    assert _run(skip) is skip


def test_only_the_asset_path_triggers_a_run():
    """A same-named file in another folder, or a backup copy, is not the asset's."""
    mtime = _ts(2025, 3, 1, 9)
    elsewhere, _ = _file("a.csv", mtime)
    backup, _ = _file("a.csv.bak", mtime)

    result = _run(
        [(elsewhere, "/exports/archive/a.csv"), (backup, "/exports/a.csv.bak")]
    )

    assert (
        isinstance(result, SkipReason)
        or not check.inst(result, SensorResult).run_requests
    )
