from dagster import Backoff, Jitter

from teamster.code_locations.kipptaf.dbt.assets import (
    core_dbt_assets,
    google_sheet_dbt_assets,
)


def test_google_sheet_dbt_assets_has_delayed_retry_policy():
    """Google Sheets external tables intermittently fail the whole dbt build with
    BigQuery reason `resourcesExceeded` ("Google Sheets service overloaded for
    spreadsheet id: ..."). dbt-bigquery cannot retry it -- `resourcesExceeded`
    maps to HTTP 400 and is in neither `_RETRYABLE_REASONS` nor
    `job_retry_reasons` -- so the step needs its own retry.
    """
    retry_policy = google_sheet_dbt_assets.op.retry_policy

    assert retry_policy is not None
    assert retry_policy.max_retries >= 3

    # The delay is the whole point. Dagster's run-level auto-retry already fires
    # on this failure but has no delay, so it re-reads the spreadsheet inside the
    # same overload window and fails identically.
    assert retry_policy.delay is not None
    assert retry_policy.delay >= 60

    assert retry_policy.backoff == Backoff.EXPONENTIAL
    assert retry_policy.jitter == Jitter.PLUS_MINUS


def test_core_dbt_assets_has_no_retry_policy():
    """The retry is scoped to the Google Sheets step. `core_dbt_assets` excludes
    `tag:google_sheet`, so it never reads a spreadsheet and a blanket retry there
    would re-run the whole warehouse build on any failure.
    """
    assert core_dbt_assets.op.retry_policy is None
