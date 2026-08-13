from teamster.libraries.finalsite.api.assets import (
    build_contacts_request_params,
    get_finalsite_since,
)

INCLUDES = {"includes": "contacts.relationships"}


def test_since_subtracts_the_safety_day():
    assert get_finalsite_since("2026-08-11") == "2026-08-10"


def test_since_crosses_a_month_boundary():
    assert get_finalsite_since("2026-08-01") == "2026-07-31"


def test_since_crosses_a_year_boundary():
    assert get_finalsite_since("2026-01-01") == "2025-12-31"


def test_incremental_run_sends_the_safety_day_since():
    assert build_contacts_request_params(
        params=INCLUDES, partition_key="2026-08-11", full_pull=False
    ) == {"includes": "contacts.relationships", "since": "2026-08-10"}


def test_full_pull_omits_since_entirely():
    """The seed path each district runs once at cutover.

    Sending `since` here would land only the contacts changed since the previous
    day, leaving staging without the ~25k-row base every later incremental
    partition is deduped against.
    """
    assert build_contacts_request_params(
        params=INCLUDES, partition_key="2026-08-11", full_pull=True
    ) == {"includes": "contacts.relationships"}


def test_unpartitioned_asset_pulls_in_full():
    assert build_contacts_request_params(
        params=INCLUDES, partition_key=None, full_pull=False
    ) == {"includes": "contacts.relationships"}


def test_caller_params_are_never_mutated():
    """`params` is captured once at asset-definition time and reused every run.

    Writing `since` into it would leak the first run's watermark into every
    later run of the same asset.
    """
    params = dict(INCLUDES)

    build_contacts_request_params(
        params=params, partition_key="2026-08-11", full_pull=False
    )

    assert params == INCLUDES


def test_missing_params_is_tolerated():
    assert build_contacts_request_params(
        params=None, partition_key="2026-08-11", full_pull=False
    ) == {"since": "2026-08-10"}
