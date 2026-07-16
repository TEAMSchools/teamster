from dagster import AssetKey, ScheduleDefinition


def test_paterson_powerschool_dlt_asset_keys():
    import yaml

    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import assets
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    config = yaml.safe_load(config_file.read_text())

    assert len(config["assets"]) == 57

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
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        assets as dlt_assets,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.schedules import (
        schedules,
    )

    expected_keys = {key for a in dlt_assets for key in a.keys}

    per_schedule_keys = [
        schedule.target.resolvable_to_job.selection.resolve(
            all_assets=dlt_assets, allow_missing=False
        )
        for schedule in schedules
    ]

    union_keys: set[AssetKey] = set()
    total = 0
    for keys in per_schedule_keys:
        union_keys |= keys
        total += len(keys)

    # No table dropped...
    assert union_keys == expected_keys
    # ...and no table scheduled in more than one tier.
    assert total == len(expected_keys)
