from dagster import DagsterInstance, build_schedule_context


def _test_dbt_code_version_schedule(schedule):
    context = build_schedule_context(
        instance=DagsterInstance.from_config(
            config_dir=".dagster/home", config_filename="dagster-cloud.yaml"
        )
    )

    output = schedule(context=context)

    context.log.info(output)


def test_kipptaf():
    from teamster.code_locations.kipptaf._dbt.schedules import dbt_code_version_schedule

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)


def test_kippnewark():
    from teamster.code_locations.kippnewark._dbt.schedules import (
        dbt_code_version_schedule,
    )

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)


def test_kippcamden():
    from teamster.code_locations.kippcamden._dbt.schedules import (
        dbt_code_version_schedule,
    )

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)


def test_kippmiami():
    from teamster.code_locations.kippmiami._dbt.schedules import (
        dbt_code_version_schedule,
    )

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)
