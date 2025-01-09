import json
from datetime import datetime, timezone

from dagster import (
    AddDynamicPartitionsRequest,
    RunRequest,
    SensorEvaluationContext,
    SensorResult,
    _check,
    sensor,
)

from teamster.code_locations.kipptaf._google.forms.assets import (
    GOOGLE_FORMS_PARTITIONS_DEF,
    responses,
)
from teamster.libraries.google.drive.resources import GoogleDriveResource
from teamster.libraries.google.forms.resources import GoogleFormsResource


@sensor(
    # trunk-ignore(pyright/reportFunctionMemberAccess)
    name=f"{responses.key.to_python_identifier()}_sensor",
    # trunk-ignore(pyright/reportArgumentType)
    target=[responses],
    minimum_interval_seconds=(15 * 60),
)
def google_forms_responses_sensor(
    context: SensorEvaluationContext,
    google_drive: GoogleDriveResource,
    google_forms: GoogleFormsResource,
):
    now = datetime.now(timezone.utc)
    run_requests = []
    cursor: dict = json.loads(context.cursor or "{}")

    for form_id in GOOGLE_FORMS_PARTITIONS_DEF.get_partition_keys(
        dynamic_partitions_store=context.instance
    ):
        timestamp = cursor.get(form_id, "1970-01-01T00:00:00Z")

        reponses = google_forms.list_responses(
            form_id=form_id, pageSize=1, filter=f"timestamp > {timestamp}"
        )

        if reponses:
            context.log.info(msg=form_id)
            run_requests.append(
                RunRequest(
                    run_key=f"{context.sensor_name}__{form_id}__{now.timestamp()}",
                    partition_key=form_id,
                )
            )
            cursor[form_id] = now.isoformat().replace("+00:00", "Z")

    # get tracked forms to partition
    forms = google_drive.list_files(
        q=(
            "mimeType='application/vnd.google-apps.form' and "
            "'1ZJAXcPfmdTDmJCqcMRje0czrwR7cF6hC' in parents"
        ),
        corpora="drive",
        driveId="0AKZ2G1Z8rxooUk9PVA",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    )

    return SensorResult(
        run_requests=run_requests,
        cursor=json.dumps(obj=cursor),
        dynamic_partitions_requests=[
            AddDynamicPartitionsRequest(
                partitions_def_name=_check.not_none(
                    value=GOOGLE_FORMS_PARTITIONS_DEF.name
                ),
                partition_keys=[f["id"] for f in forms],
            )
        ],
    )


sensors = [
    google_forms_responses_sensor,
]
