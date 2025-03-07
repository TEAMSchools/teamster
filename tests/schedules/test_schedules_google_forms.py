from dagster import DagsterInstance, build_schedule_context

from teamster.code_locations.kipptaf._google.forms.schedules import (
    google_forms_asset_job_schedule,
)


def test_schedule():
    context = build_schedule_context(
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        )
    )

    output = google_forms_asset_job_schedule(context=context)

    assert output is not None

    # trunk-ignore(pyright/reportGeneralTypeIssues)
    for o in output:
        context.log.info(o)
