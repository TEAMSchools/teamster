import json

from dagster import DagsterInstance, SensorResult, build_sensor_context

from teamster.code_locations.kipptaf._google.forms.sensors import (
    google_forms_responses_sensor,
)
from teamster.code_locations.kipptaf.resources import (
    get_google_drive_resource,
    get_google_forms_resource,
)


def test_google_forms_responses_sensor():
    cursor = {
        "1jpeMof_oQ9NzTw85VFsA5A7G9VrH3XkSc_nZDFz07nA": "2025-01-09T17:52:11.213611Z",
        "1cvp9RnYxbn-WGLXsYSupbEl2KhVhWKcOFbHR2CgUBH0": "2025-01-09T17:52:11.213611Z",
        "1IXIrXFLrXDyq9cvjMBhFJB9mV_nxKGUNYUlRbD4ku_A": "2025-01-09T17:52:11.213611Z",
        "1tuqQIkPX8GfGXdpkNra9shB2Ig_U9CSS7VH1RfuQ_68": "2025-01-09T17:52:11.213611Z",
        "1oUBls4Kaj0zcbQyeWowe8Es1BFqunolAPEamzT6enQs": "2025-01-09T17:52:11.213611Z",
        "1YdgXFZE1yjJa-VfpclZrBtxvW0w4QvxNrvbDUBxIiWI": "2025-01-09T17:52:11.213611Z",
        "15xuEO72xhyhhv8K0qKbkSV864-DetXhmWsxKyS7ai50": "2025-01-09T17:52:11.213611Z",
        "1qfXBcMxp9712NEnqOZS2S-Zm_SAvXRi_UndXxYZUZho": "2025-01-09T17:52:11.213611Z",
        "15Iq_dMeOmURb68Bg8Uc6j-Fco4N2wix7D8YFfSdCKPE": "2025-01-09T17:52:11.213611Z",
        "16pr-UXHqY9g4kzB6azIWm0MRQANNspzWtAjvNEVcaUo": "2025-01-09T17:52:11.213611Z",
        "1qFzdciQdg7g9aNujUulk6hivP7Qkz4Ab4Hr5WzW_k1Q": "2025-01-09T17:52:11.213611Z",
        "1SoCq9ZlmpvHjquepv4ei1XhtRWR0Vo7vbJE0sBz3yxo": "2025-01-09T17:52:11.213611Z",
        "1jXlqIoHowVUPxGfzuNxrNRMWO7zMQe71fqKpzpIbA3g": "2025-01-09T17:52:11.213611Z",
    }

    sensor_result = google_forms_responses_sensor(
        context=build_sensor_context(
            instance=DagsterInstance.from_config(
                config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
            ),
            sensor_name=google_forms_responses_sensor.name,
            cursor=json.dumps(obj=cursor),
        ),
        google_forms=get_google_forms_resource(
            test=True,
            service_account_file_path=(
                "/etc/secret-volume/gcloud_dagster_service_account.json"
            ),
        ),
        google_drive=get_google_drive_resource(
            test=True,
            service_account_file_path=(
                "/etc/secret-volume/gcloud_dagster_service_account.json"
            ),
        ),
    )

    assert isinstance(sensor_result, SensorResult)

    assert sensor_result.run_requests is not None
    assert sensor_result.dynamic_partitions_requests is not None

    assert len(sensor_result.run_requests) > 0
    assert len(sensor_result.dynamic_partitions_requests) > 0
