import json

from dagster import SensorResult, build_sensor_context

from teamster.libraries.google.drive.resources import GoogleDriveResource


def test_google_sheets_asset_sensor():
    from teamster.code_locations.kipptaf.google.sheets.sensors import (
        google_sheets_asset_sensor,
    )

    cursor: dict[str, float] = {}

    sensor_result = google_sheets_asset_sensor(
        context=build_sensor_context(
            cursor=json.dumps(obj=cursor), sensor_name=google_sheets_asset_sensor.name
        ),
        google_drive=GoogleDriveResource(
            service_account_file_path=(
                "/etc/secret-volume/gcloud_dagster_service_account.json"
            ),
        ),
    )

    assert isinstance(sensor_result, SensorResult)
    assert len(sensor_result.asset_events) > 0
