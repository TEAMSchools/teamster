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
        MultiPartitionKey,
        MultiPartitionsDefinition,
        RunRequest,
        StaticPartitionsDefinition,
        asset,
    )
    from dagster_shared import check

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

        return sorted(
            check.inst(r.partition_key, MultiPartitionKey).keys_by_dimension["date"]
            for r in run_requests
        )

    assert dates(0) == ["2026-07-01", "2026-08-01", "2026-09-01"]
    assert dates(1) == ["2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01"]


def _executor_name(asset_count: int, schedule_name: str, **kwargs) -> str:
    from dagster import Definitions, StaticPartitionsDefinition, asset

    from teamster.libraries.deanslist.schedules import build_deanslist_job_schedule

    partitions_def = StaticPartitionsDefinition(["1"])

    @asset(partitions_def=partitions_def)
    def a1(): ...

    @asset(partitions_def=partitions_def)
    def a2(): ...

    assets = [a1, a2][:asset_count]
    schedule = build_deanslist_job_schedule(
        schedule_name=schedule_name,
        cron_schedule="0 0 * * *",
        execution_timezone="America/New_York",
        asset_selection=assets,
        **kwargs,
    )

    defs = Definitions(assets=assets, schedules=[schedule])

    return defs.resolve_job_def(schedule.job_name).executor_def.name


def test_deanslist_single_asset_runs_in_process():
    assert (
        _executor_name(1, "x__deanslist__month_partitioned_asset_job_schedule")
        == "in_process"
    )


def test_deanslist_multi_asset_runs_multiprocess():
    assert (
        _executor_name(2, "x__deanslist__static_partitioned_asset_job_schedule")
        == "multiprocess"
    )


def test_deanslist_explicit_job_name():
    assert (
        _executor_name(
            1,
            "x__deanslist__midday_commlog_job",
            job_name="x__deanslist__midday_commlog_asset_job",
        )
        == "in_process"
    )


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
