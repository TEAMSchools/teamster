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
