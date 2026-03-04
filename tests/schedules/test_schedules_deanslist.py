from dagster import DagsterInstance, build_schedule_context


def _test_schedule(schedule):
    context = build_schedule_context(instance=DagsterInstance.get())

    output = schedule(context=context)

    for o in output:
        context.log.info(o)


def test_deanslist_static_partitioned_assets_job_schedule_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.schedules import (
        deanslist_static_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_static_partitioned_assets_job_schedule)


def test_deanslist_midday_commlog_job_schedule_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.schedules import (
        deanslist_midday_commlog_job_schedule,
    )

    _test_schedule(deanslist_midday_commlog_job_schedule)


def test_deanslist_deanslist_month_partitioned_assets_job_schedule_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.schedules import (
        deanslist_month_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_month_partitioned_assets_job_schedule)


def test_deanslist_deanslist_year_partitioned_assets_job_schedule_kippcamden():
    from teamster.code_locations.kippcamden.deanslist.schedules import (
        deanslist_year_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_year_partitioned_assets_job_schedule)


def test_deanslist_static_partitioned_assets_job_schedule_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.schedules import (
        deanslist_static_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_static_partitioned_assets_job_schedule)


def test_deanslist_midday_commlog_job_schedule_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.schedules import (
        deanslist_midday_commlog_job_schedule,
    )

    _test_schedule(deanslist_midday_commlog_job_schedule)


def test_deanslist_deanslist_month_partitioned_assets_job_schedule_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.schedules import (
        deanslist_month_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_month_partitioned_assets_job_schedule)


def test_deanslist_deanslist_year_partitioned_assets_job_schedule_kippmiami():
    from teamster.code_locations.kippmiami.deanslist.schedules import (
        deanslist_year_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_year_partitioned_assets_job_schedule)


def test_deanslist_static_partitioned_assets_job_schedule_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.schedules import (
        deanslist_static_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_static_partitioned_assets_job_schedule)


def test_deanslist_midday_commlog_job_schedule_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.schedules import (
        deanslist_midday_commlog_job_schedule,
    )

    _test_schedule(deanslist_midday_commlog_job_schedule)


def test_deanslist_deanslist_month_partitioned_assets_job_schedule_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.schedules import (
        deanslist_month_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_month_partitioned_assets_job_schedule)


def test_deanslist_deanslist_year_partitioned_assets_job_schedule_kippnewark():
    from teamster.code_locations.kippnewark.deanslist.schedules import (
        deanslist_year_partitioned_assets_job_schedule,
    )

    _test_schedule(deanslist_year_partitioned_assets_job_schedule)
