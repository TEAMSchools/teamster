import json

from dagster import SensorResult, build_sensor_context

from teamster.code_locations.kipptaf._google.sheets.sensors import (
    google_sheets_asset_sensor,
)
from teamster.libraries.google.sheets.resources import GoogleSheetsResource


def test_google_sheets_asset_sensor():
    cursor = {
        # "1jMnltTr0cqJ5c1tlfyzySZ87eNaU6frCOD7E8f7FUc8": 1727377153.342,
        # "1G2z9rwXsFaMdFL6iOYdfQTVjZ7bctXMyz_Q09IhP4QE": 1728348682.704,
        # "1XCOY8t6dlSaS8NKdZCKCwdMmp_0FRTrBih3a-wyROm4": 1716302879.648,
        # "1FCc28XWxFj3gSfItGGJ2tVU0C1fYD1JxKRxuSFqisMo": 1721053838.473,
        # "1hsYwXwi0iMMyurG6aklhaY_X0T-Mk3250ERDrF_bhjU": 1716303067.837,
        # "1azcq9FsGDjYpvK7VBIHtGOsY8Yd-E5hFrxWuk5hFLH0": 1728423396.46,
        # "1j7sBEH-PrkHTv83y3pYrgOPQvRm7S6vdXESbR_OYNFE": 1727440521.781,
        # "15PIpnnKaU2NF42JzjUbnrocL_2F41JOVZP4dYDS7mME": 1716303046.749,
        # "1yCW2pmQYwLQuTel72QWCyq83qlyQEemYbONLPAIvy7c": 1727370643.383,
        # "1OvJ95fuDCWVu9YQoVZnjauC8mdpgL4BmqdfqvgT7gAw": 1716903036.679,
        # "1bMHQ2qaVdOcz4fDsl5CnWUBmVwl-JkDD_aj-sHfgn5I": 1721916055.32,
        # "1xPzM3XM3-5e343VkH75rz5fsQlO4z0BsPNh3xAWvPQ4": 1724964706.639,
        # "1pVY5ByKU03s8kfrd9ori1m6Sa-xOTJR9Qt0eFkkKycM": 1716909328.451,
        # "1t6aN_0Bd6KUUmVcz7WSAzolToAW-3Cf4AV0ZkBFseiY": 1716993916.942,
        # "1smCSUKz2SXwnohmz59LNptoN5jHzYD2TfZNHZwK7Dts": 1725468249.812,
        # "15u_nUWcJY5-3V2xT0ZvICkQ1nrpGuMI2LAy5UMmUbNs": 1728420471.042,
        # "1bRd3cI3WlTdizm5ja7IxGxGjJDzXrOX6i2G731h9yr8": 1727660168.343,
    }

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
