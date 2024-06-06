from dagster import (
    AddDynamicPartitionsRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)

from teamster.code_locations.kipptaf import CODE_LOCATION
from teamster.code_locations.kipptaf.google.forms.assets import (
    GOOGLE_FORMS_PARTITIONS_DEF,
)
from teamster.libraries.google.drive.resources import GoogleDriveResource


@sensor(
    name=f"{CODE_LOCATION}_google_forms_partition_sensor",
    minimum_interval_seconds=(60 * 10),
)
def google_forms_partition_sensor(
    context: SensorEvaluationContext, google_drive: GoogleDriveResource
):
    files = google_drive.list_files(
        q="mimeType='application/vnd.google-apps.form' and '1ZJAXcPfmdTDmJCqcMRje0czrwR7cF6hC' in parents",
        corpora="drive",
        driveId="0AKZ2G1Z8rxooUk9PVA",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    )

    return SensorResult(
        dynamic_partitions_requests=[
            AddDynamicPartitionsRequest(
                partitions_def_name=_check.not_none(
                    value=GOOGLE_FORMS_PARTITIONS_DEF.name
                ),
                partition_keys=[f["id"] for f in files],
            )
        ]
    )


sensors = [
    google_forms_partition_sensor,
]
