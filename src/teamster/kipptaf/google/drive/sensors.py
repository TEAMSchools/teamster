from dagster import (
    AddDynamicPartitionsRequest,
    SensorEvaluationContext,
    SensorResult,
    sensor,
)

from teamster.google.drive.resources import GoogleDriveResource
from teamster.kipptaf import CODE_LOCATION
from teamster.kipptaf.google.forms.assets import GOOGLE_FORMS_PARTITIONS_DEF


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
                partitions_def_name=GOOGLE_FORMS_PARTITIONS_DEF.name,  # type: ignore
                partition_keys=[f["id"] for f in files],
            )
        ]
    )


sensors = [
    google_forms_partition_sensor,
]
