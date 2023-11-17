from dagster import build_schedule_context

from teamster.core.utils.functions import get_dagster_cloud_instance


def _test_dbt_code_version_schedule(schedule):
    context = build_schedule_context(
        instance=get_dagster_cloud_instance("/workspaces/teamster/.dagster/home")
    )

    output = schedule(context=context)

    context.log.info(output)


def test_kipptaf():
    from teamster.kipptaf.dbt.schedules import dbt_code_version_schedule

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)


def test_kippnewark():
    from teamster.kippnewark.dbt.schedules import dbt_code_version_schedule

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)


def test_kippcamden():
    from teamster.kippcamden.dbt.schedules import dbt_code_version_schedule

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)


def test_kippmiami():
    from teamster.kippmiami.dbt.schedules import dbt_code_version_schedule

    _test_dbt_code_version_schedule(schedule=dbt_code_version_schedule)
