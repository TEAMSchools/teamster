import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf.google.sheets.sensors import (
    google_sheets_asset_sensor,
)
from teamster.libraries.google.sheets.resources import GoogleSheetsResource


def test_google_sheets_asset_sensor():
    cursor = {}

    sensor_result = google_sheets_asset_sensor(
        context=build_sensor_context(
            cursor=json.dumps(obj=cursor), sensor_name=google_sheets_asset_sensor.name
        ),
        gsheets=GoogleSheetsResource(
            service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
        ),
    )

    assert isinstance(sensor_result, SensorResult)
    assert len(sensor_result.asset_events) > 0
