from dagster import DagsterInstance, build_schedule_context


def test_schedule():
    from teamster.code_locations.kipptaf.google.forms.schedules import (
        google_forms_asset_job_schedule,
    )

    context = build_schedule_context(
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        )
    )

    from teamster.core.resources import GOOGLE_DRIVE_RESOURCE

    output = google_forms_asset_job_schedule(
        context=context, google_drive=GOOGLE_DRIVE_RESOURCE
    )

    assert output is not None

    # trunk-ignore(pyright/reportGeneralTypeIssues)
    for o in output:
        context.log.info(o)


def _forms_run_keys(modified: dict[str, float], tick=None) -> list[str]:
    from types import SimpleNamespace

    from dagster import instance_for_test

    from teamster.code_locations.kipptaf.google.forms.assets import (
        GOOGLE_FORMS_PARTITIONS_DEF,
    )
    from teamster.code_locations.kipptaf.google.forms.schedules import (
        google_forms_asset_job_schedule,
    )

    drive = SimpleNamespace(get_modified_times=lambda file_ids, logger=None: modified)

    # the schedule context needs a persistent instance, not an ephemeral one
    with instance_for_test() as instance:
        instance.add_dynamic_partitions(
            partitions_def_name=str(GOOGLE_FORMS_PARTITIONS_DEF.name),
            partition_keys=["a", "b", "c"],
        )
        context = build_schedule_context(
            instance=instance,
            resources={"google_drive": drive},
            scheduled_execution_time=tick,
        )

        return sorted(
            # trunk-ignore(pyright/reportOptionalIterable,pyright/reportGeneralTypeIssues)
            str(r.partition_key)
            for r in google_forms_asset_job_schedule(context=context)
        )


def test_forms_schedule_requests_only_recent_edits():
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    tick = datetime(2026, 11, 3, tzinfo=ZoneInfo("America/New_York"))

    # "c" is missing: its Drive lookup failed, so it still gets a run
    keys = _forms_run_keys(
        {
            "a": (tick - timedelta(hours=1)).timestamp(),
            "b": (tick - timedelta(hours=26)).timestamp(),
        },
        tick=tick,
    )

    assert keys == ["a", "c"]


def test_forms_schedule_without_tick_time_uses_now():
    import time

    keys = _forms_run_keys(
        {"a": time.time() - 60, "b": time.time() - 3 * 86400, "c": 0.0}
    )

    assert keys == ["a"]


def test_forms_schedule_runs_in_process():
    from teamster.code_locations.kipptaf.google.forms.schedules import (
        google_forms_asset_job,
        google_forms_asset_job_schedule,
    )

    assert google_forms_asset_job_schedule.job_name == (
        "kipptaf__google__forms__form_asset_job"
    )
    assert google_forms_asset_job.executor_def is not None
    assert google_forms_asset_job.executor_def.name == "in_process"
