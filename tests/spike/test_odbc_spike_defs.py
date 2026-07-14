"""Definition-time checks for the throwaway PowerSchool ODBC spike assets.

These run in the Codespace with no PowerSchool credentials — they only assert
that the modules import cleanly (lazy env reads) and produce the expected
asset keys.
"""

from dagster import AssetKey


def test_dlt_spike_asset_keys():
    from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.dlt_assets import (
        DLT_SPIKE_ASSETS,
        SPIKE_TABLES,
    )

    assert set(SPIKE_TABLES) == {"students", "storedgrades", "assignmentscore"}

    keys = {key for a in DLT_SPIKE_ASSETS for key in a.keys}
    assert keys == {
        AssetKey(["kipppaterson", "powerschool", "spike", "dlt", t])
        for t in SPIKE_TABLES
    }
