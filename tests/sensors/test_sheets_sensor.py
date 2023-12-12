from dagster import build_sensor_context, instance_for_test

from teamster.kipptaf.google.resources import GoogleSheetsResource
from teamster.kipptaf.google.sheets.assets import build_gsheet_asset
from teamster.kipptaf.google.sheets.sensors import google_sheets_asset_sensor

test_asset = build_gsheet_asset(
    source_name="",
    name="standards_translation",
    uri="https://docs.google.com/spreadsheets/d/1EwHv7MajgHTq-HphLpwrS0KG_2Y_FXlPuPvj98YuFS8",
    range_name="standards_translation",
)


def test_sensor():
    with instance_for_test() as instance:
        google_sheets_asset_sensor(
            build_sensor_context(
                instance=instance,
                resources={
                    "gsheets": GoogleSheetsResource(
                        service_account_file_path="/etc/secret-volume/gcloud_service_account_json"
                    )
                },
            )
        )
