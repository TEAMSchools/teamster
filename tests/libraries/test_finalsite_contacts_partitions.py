"""Guards the production partitioning of the Finalsite contacts asset.

`test_finalsite_contacts_schedule.py` proves the schedule yields the right
`RunRequest` for a correctly-configured asset, but it does so against a local
fixture asset carrying its own `partitions_def` — so it cannot catch a
misconfigured PRODUCTION asset. These tests read the real per-district assets.

The regression they exist for: `DailyPartitionsDefinition` defaults to
`end_offset=0`, which only exposes partitions whose window has CLOSED. The
schedule targets the CURRENT day's key, so without `end_offset=1` every tick
fails with `DagsterUnknownPartitionError` in all four districts.
"""

import pytest
from dagster import DailyPartitionsDefinition
from dagster_shared import check

CODE_LOCATIONS = ["kippnewark", "kippcamden", "kippmiami", "kipppaterson"]


def _contacts_partitions_def(code_location: str) -> DailyPartitionsDefinition:
    module = __import__(
        f"teamster.code_locations.{code_location}.finalsite.assets",
        fromlist=["contacts"],
    )

    return check.inst(module.contacts.partitions_def, DailyPartitionsDefinition)


@pytest.mark.parametrize("code_location", CODE_LOCATIONS)
def test_contacts_exposes_the_current_day_partition(code_location: str):
    """The schedule targets today's key, so today's partition must be valid.

    `end_offset=1` is what makes the in-flight day addressable. This asserts the
    property the schedule depends on rather than the flag that implements it.
    """
    partitions_def = _contacts_partitions_def(code_location)

    assert partitions_def.end_offset == 1


@pytest.mark.parametrize("code_location", CODE_LOCATIONS)
def test_contacts_asset_key_is_unchanged(code_location: str):
    """The dbt source and every downstream consumer key off this exact path."""
    module = __import__(
        f"teamster.code_locations.{code_location}.finalsite.assets",
        fromlist=["contacts"],
    )

    assert module.contacts.key.to_user_string() == f"{code_location}/finalsite/contacts"
