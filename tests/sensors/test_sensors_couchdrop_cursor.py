import json
from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from dagster import SensorResult, asset, build_sensor_context
from dagster_shared import check

from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor


@asset(
    key=["test", "kept"], metadata={"remote_dir_regex": "/x", "remote_file_regex": "f"}
)
def kept(): ...


def test_stale_cursor_keys_pruned():
    sensor = build_couchdrop_sftp_sensor(
        code_location="test",
        local_timezone=ZoneInfo("America/New_York"),
        asset_selection=[kept],
        minimum_interval_seconds=60,
        folder_id="x",
    )

    calls = []
    google_drive = SimpleNamespace(
        files_list_recursive=lambda **kwargs: calls.append(kwargs) or []
    )

    context = build_sensor_context(
        cursor=json.dumps({"test__kept": 100, "test__dropped": 0})
    )

    result = check.inst(
        sensor(context=context, google_drive=google_drive), SensorResult
    )

    assert json.loads(check.not_none(result.cursor)) == {"test__kept": 100}
    assert calls[0]["min_modified_time"] == datetime.fromtimestamp(100, tz=UTC)
