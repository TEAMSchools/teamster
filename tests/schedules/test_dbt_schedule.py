from dagster import DagsterInstance, build_schedule_context


def _test_dbt_code_version_schedule(schedule):
    context = build_schedule_context(instance=DagsterInstance.get())

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
