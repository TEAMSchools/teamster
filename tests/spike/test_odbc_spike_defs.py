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


def test_sling_spike_asset_keys():
    from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.dlt_assets import (
        SPIKE_TABLES,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.odbc_spike.sling_assets import (
        SLING_SPIKE_ASSETS,
    )

    keys = {key for a in SLING_SPIKE_ASSETS for key in a.keys}
    assert keys == {
        AssetKey(["kipppaterson", "powerschool", "spike", "sling", t])
        for t in SPIKE_TABLES
    }


def test_kipppaterson_definitions_include_spike_assets():
    from teamster.code_locations.kipppaterson.definitions import defs

    for table in ("students", "storedgrades", "assignmentscore"):
        for tool in ("dlt", "sling"):
            key = AssetKey(["kipppaterson", "powerschool", "spike", tool, table])
            assert defs.get_assets_def(key) is not None
