"""Definition-time checks for the PowerSchool dlt asset factory.

Run in the Codespace with no PowerSchool credentials — assert the module
imports cleanly (lazy env reads) and produces the expected asset keys.
"""

import pytest
from dagster import AssetKey


def test_powerschool_dlt_asset_key():
    from teamster.libraries.dlt.powerschool.assets import (
        build_powerschool_dlt_assets,
    )

    assets_def = build_powerschool_dlt_assets(
        code_location="kipppaterson", table_name="students"
    )

    assert set(assets_def.keys) == {
        AssetKey(["kipppaterson", "powerschool", "students"])
    }
    assert assets_def.op.name == "kipppaterson__powerschool__students"


def test_powerschool_dlt_rejects_unknown_load_strategy():
    from teamster.libraries.dlt.powerschool.assets import (
        build_powerschool_dlt_assets,
    )

    with pytest.raises(ValueError, match="load_strategy"):
        build_powerschool_dlt_assets(
            code_location="kipppaterson",
            table_name="students",
            load_strategy="merge",
        )
