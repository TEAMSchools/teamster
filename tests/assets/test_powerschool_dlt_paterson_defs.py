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
        AssetKey(["kipppaterson", "powerschool", "sis", a["table_name"]])
        for a in config["assets"]
    }


def test_paterson_powerschool_dlt_triggers():
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import (
        schedules,
        sensors,
    )

    by_name = {s.name: s for s in schedules.schedules}

    nightly = by_name["kipppaterson__powerschool__dlt__nightly_asset_job_schedule"]

    assert isinstance(nightly, ScheduleDefinition)
    assert nightly.cron_schedule == "0 2 * * *"
    assert len(schedules.schedules) == 1  # intraday schedule replaced by sensor

    (sensor_def,) = sensors.sensors
    assert sensor_def.name == "kipppaterson__powerschool__dlt__intraday_sensor"


def test_paterson_powerschool_dlt_triggers_cover_every_table():
    """Every configured table belongs to at least one trigger.

    A table with both membership flags false would silently never
    materialize (the dlt assets carry no automation condition). The overlap
    between tiers must be exactly the no-cursor set: count-gated intraday,
    authoritative overnight.
    """
    import yaml

    from teamster.code_locations.kipppaterson.powerschool.sis.dlt import (
        schedules as schedules_module,
    )
    from teamster.code_locations.kipppaterson.powerschool.sis.dlt.assets import (
        config_file,
    )

    config = yaml.safe_load(config_file.read_text())

    def key(name):
        return f"kipppaterson/powerschool/sis/{name}"

    expected = {key(a["table_name"]) for a in config["assets"]}
    intraday = {key(a["table_name"]) for a in config["assets"] if a["intraday"]}
    no_cursor = {
        key(a["table_name"]) for a in config["assets"] if a["cursor_column"] is None
    }

    # Resolve nightly targets through the real scheduling function — the exact
    # code an orphaned membership would route around.
    nightly = set(schedules_module._nightly_targets())

    assert intraday | nightly == expected
    assert intraday & nightly == no_cursor
