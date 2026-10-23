from dagster import DagsterInstance, build_schedule_context


def _test_schedule(schedule):
    context = build_schedule_context(instance=DagsterInstance.get())

    output = schedule(context=context)

    for o in output:
        context.log.info(o)


def test_deanslist_schedule_lookback_months():
    from collections.abc import Iterator
    from datetime import datetime
    from typing import cast

    from dagster import (
        MonthlyPartitionsDefinition,
        MultiPartitionsDefinition,
        RunRequest,
        StaticPartitionsDefinition,
        asset,
    )

    from teamster.core.utils.classes import FiscalYear
    from teamster.libraries.deanslist.schedules import build_deanslist_job_schedule

    @asset(
        partitions_def=MultiPartitionsDefinition(
            {
                "school": StaticPartitionsDefinition(["1"]),
                "date": MonthlyPartitionsDefinition(
                    start_date="2026-04-01", end_date="2026-10-01"
                ),
            }
        )
    )
    def incidents(): ...

    def dates(lookback_months: int) -> list[str]:
        schedule = build_deanslist_job_schedule(
            schedule_name="test",
            cron_schedule="0 0 * * *",
            execution_timezone="America/New_York",
            asset_selection=[incidents],
            current_fiscal_year=FiscalYear(
                datetime=datetime(2026, 10, 23), start_month=7
            ),
            lookback_months=lookback_months,
        )

        run_requests = cast(
            "Iterator[RunRequest]", schedule(context=build_schedule_context())
        )

        return sorted(str(r.partition_key).split("|")[0] for r in run_requests)

    assert dates(0) == ["2026-07-01", "2026-08-01", "2026-09-01"]
    assert dates(1) == ["2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01"]


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
