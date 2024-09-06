from dagster import DagsterInstance, build_schedule_context

from teamster.core.resources import (
    get_db_powerschool_resource,
    get_ssh_powerschool_resource,
)


def _test(schedule, ssh_powerschool, db_powerschool):
    with build_schedule_context(
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        ),
        resources={
            "ssh_powerschool": ssh_powerschool,
            "db_powerschool": db_powerschool,
        },
    ) as context:
        output = schedule(context=context)

    for o in output:
        context.log.info(o)


def test_schoolmint_grow_observations_asset_job_schedule():
    from teamster.code_locations.kippnewark import CODE_LOCATION
    from teamster.code_locations.kippnewark.powerschool.schedules import (
        powerschool_sis_asset_gradebook_schedule,
    )

    _test(
        schedule=powerschool_sis_asset_gradebook_schedule,
        ssh_powerschool=get_ssh_powerschool_resource(CODE_LOCATION.upper()),
        db_powerschool=get_db_powerschool_resource(CODE_LOCATION.upper()),
    )
