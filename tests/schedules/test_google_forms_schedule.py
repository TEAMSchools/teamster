from dagster import build_schedule_context

from teamster.kipptaf.google.forms.schedules import google_forms_asset_job_schedule


def test_schedule():
    context = build_schedule_context()

    output = google_forms_asset_job_schedule(context=context)

    for o in output:
        context.log.info(o)
