from datetime import datetime
from zoneinfo import ZoneInfo

from dagster import (
    DagsterInstance,
    DailyPartitionsDefinition,
    Definitions,
    asset,
    build_schedule_context,
)

from teamster.libraries.finalsite.api.schedules import (
    build_finalsite_contacts_schedule,
)

TIMEZONE = "America/New_York"


@asset(
    key=["test", "finalsite", "contacts"],
    # end_offset=1 mirrors the production partitions_def (see the four
    # code-location finalsite/assets.py files) -- without it today's partition
    # doesn't exist until tomorrow, and this fixture would not reproduce the
    # DagsterUnknownPartitionError the production defect actually raised.
    partitions_def=DailyPartitionsDefinition(
        start_date="2026-08-01", timezone=TIMEZONE, end_offset=1
    ),
)
def _contacts() -> None: ...


def _run_requests_at(hour: int, minute: int):
    schedule = build_finalsite_contacts_schedule(
        code_location="test",
        execution_timezone=TIMEZONE,
        asset_selection=[_contacts],
    )

    defs = Definitions(assets=[_contacts], schedules=[schedule])

    context = build_schedule_context(
        instance=DagsterInstance.ephemeral(),
        scheduled_execution_time=datetime(
            2026, 8, 11, hour, minute, tzinfo=ZoneInfo(TIMEZONE)
        ),
        repository_def=defs.get_repository_def(),
    )

    return list(schedule.evaluate_tick(context).run_requests or [])


def test_overnight_tick_targets_todays_partition():
    run_requests = _run_requests_at(hour=0, minute=15)

    assert len(run_requests) == 1
    assert run_requests[0].partition_key == "2026-08-11"


def test_midday_tick_targets_the_same_partition():
    run_requests = _run_requests_at(hour=12, minute=0)

    assert len(run_requests) == 1
    assert run_requests[0].partition_key == "2026-08-11"


def test_run_key_is_none_so_the_second_daily_tick_is_not_deduplicated():
    # Both ticks target the same partition key. A run_key equal to the partition
    # key would make Dagster's idempotency silently swallow the 12:00 run.
    assert _run_requests_at(hour=0, minute=15)[0].run_key is None


def test_max_runtime_tag_is_bounded_for_an_incremental_pull():
    tags = _run_requests_at(hour=0, minute=15)[0].tags

    assert tags["dagster/max_runtime"] == "900"


def test_schedule_name_matches_the_existing_dagster_plus_object():
    schedule = build_finalsite_contacts_schedule(
        code_location="test",
        execution_timezone=TIMEZONE,
        asset_selection=[_contacts],
    )

    assert schedule.name == "test__finalsite__contacts__daily_asset_job_schedule"
