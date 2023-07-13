from dagster import build_sensor_context, instance_for_test

from teamster.core.google.sheets.assets import build_gsheet_asset
from teamster.core.google.sheets.resources import GoogleSheetsResource
from teamster.core.google.sheets.sensors import build_gsheet_sensor

CODE_LOCATION = "kipptaf"

test_asset = build_gsheet_asset(
    code_location=CODE_LOCATION,
    sheet_id="1EwHv7MajgHTq-HphLpwrS0KG_2Y_FXlPuPvj98YuFS8",
    name="standards_translation",
    range_name="standards_translation",
)

gsheets_sensor = build_gsheet_sensor(
    code_location=CODE_LOCATION, asset_defs=[test_asset]
)


def test_sensor():
    with instance_for_test() as instance:
        gsheets_sensor(
            build_sensor_context(
                instance=instance,
                resources={
                    "gsheets": GoogleSheetsResource(
                        service_account_file_path="env/gcloud_service_account_json"
                    )
                },
            )
        )
