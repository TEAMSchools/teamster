from dagster import DagsterInstance, build_schedule_context


def _test(schedule, ps_enrollment):
    with build_schedule_context(
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        ),
        resources={"ps_enrollment": ps_enrollment},
    ) as context:
        output = schedule(context=context)

    for o in output:
        context.log.info(o)


def test_powerschool_sis_asset_gradebook_schedule_kippnewark():
    from teamster.code_locations.kipptaf.powerschool.enrollment.schedules import (
        pse_submission_records_schedule,
    )
    from teamster.code_locations.kipptaf.resources import (
        POWERSCHOOL_ENROLLMENT_RESOURCE,
    )

    _test(
        schedule=pse_submission_records_schedule,
        ps_enrollment=POWERSCHOOL_ENROLLMENT_RESOURCE,
    )
