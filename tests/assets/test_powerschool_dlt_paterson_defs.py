from dagster import AssetKey, ScheduleDefinition


def test_paterson_powerschool_dlt_asset_keys():
    import yaml

    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import assets
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    config = yaml.safe_load(config_file.read_text())

    assert len(config["assets"]) == 48

    keys = {key for a in assets.assets for key in a.keys}
    assert keys == {
        AssetKey(["kipppaterson", "powerschool", a["table_name"]])
        for a in config["assets"]
    }


def test_paterson_powerschool_dlt_schedules():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import (
        schedules,
    )

    by_name = {s.name: s for s in schedules.schedules}

    intraday = by_name["kipppaterson__powerschool__dlt__intraday_asset_job_schedule"]
    nightly = by_name["kipppaterson__powerschool__dlt__nightly_asset_job_schedule"]

    assert isinstance(intraday, ScheduleDefinition)
    assert intraday.cron_schedule == "*/15 * * * *"
    assert nightly.cron_schedule == "0 2 * * *"


def test_paterson_powerschool_dlt_schedules_cover_every_table_exactly_once():
    """Every configured table is scheduled in exactly one of the two tiers.

    `_tier_targets()` filters by exact-match `schedule_tier` — a misspelled
    tier would silently drop a table from BOTH schedules, and since the dlt
    assets carry no automation condition, it would never materialize (a
    silent data gap). This asserts the union of the two schedules' resolved
    asset selections equals the full configured asset-key set, with no
    drops and no duplicates.
    """
    import yaml

    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import (
        schedules as schedules_module,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    config = yaml.safe_load(config_file.read_text())
    expected = {f"kipppaterson/powerschool/{a['table_name']}" for a in config["assets"]}

    # Resolve targets through the real scheduling function — the exact code a
    # typo'd tier would silently route around.
    intraday = schedules_module._tier_targets("intraday")
    nightly = schedules_module._tier_targets("nightly")

    # No table dropped...
    assert set(intraday) | set(nightly) == expected
    # ...and no table scheduled in more than one tier.
    assert len(intraday) + len(nightly) == len(expected)
