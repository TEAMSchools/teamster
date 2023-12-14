import json

from dagster import build_sensor_context

from teamster.kipptaf.google.resources import GoogleSheetsResource
from teamster.kipptaf.google.sheets.sensors import google_sheets_asset_sensor


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

    # trunk-ignore(bandit/B101)
    assert len(sensor_result.asset_events) > 0  # type: ignore
