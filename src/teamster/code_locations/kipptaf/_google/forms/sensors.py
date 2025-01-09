import json
from datetime import datetime, timezone

from dagster import RunRequest, SensorEvaluationContext, SensorResult, sensor

from teamster.code_locations.kipptaf._google.forms.assets import (
    GOOGLE_FORMS_PARTITIONS_DEF,
    responses,
)
from teamster.libraries.google.forms.resources import GoogleFormsResource


@sensor(
    # trunk-ignore(pyright/reportFunctionMemberAccess)
    name=f"{responses.key.to_python_identifier()}_sensor",
    # trunk-ignore(pyright/reportArgumentType)
    target=[responses],
    minimum_interval_seconds=(15 * 60),
)
def google_forms_responses_sensor(
    context: SensorEvaluationContext, google_forms: GoogleFormsResource
):
    now = datetime.now(timezone.utc)
    run_requests = []

    cursor: dict = json.loads(context.cursor or "{}")
    partition_keys = GOOGLE_FORMS_PARTITIONS_DEF.get_partition_keys(
        dynamic_partitions_store=context.instance
    )

    for form_id in partition_keys:
        timestamp = cursor.get(form_id, "1970-01-01T00:00:00Z")

        reponses = google_forms.list_responses(
            form_id=form_id, pageSize=1, filter=f"timestamp > {timestamp}"
        )

        if reponses:
            context.log.info(msg=form_id)
            run_requests.append(
                RunRequest(
                    run_key=f"{context.sensor_name}_{form_id}", partition_key=form_id
                )
            )
            cursor[form_id] = now.isoformat().replace("+00:00", "Z")

    return SensorResult(run_requests=run_requests, cursor=json.dumps(obj=cursor))


sensors = [
    google_forms_responses_sensor,
]
