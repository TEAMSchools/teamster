from dagster import config_from_files

from teamster.core.powerschool.db.assets import table_asset_factory
from teamster.kippnewark import CODE_LOCATION, POWERSCHOOL_PARTITION_START_DATE

# TODO: rename to something like "full" or "non-partition"
ps_daily_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        freshness_policy={"maximum_lag_minutes": 0, "cron_schedule": "0 0 * * *"},
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-daily.yaml"]
    )["assets"]
]

ps_misc_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-misc.yaml"]
    )["assets"]
]

ps_transactiondate_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
        where_column="transaction_date",
    )
    for cfg in config_from_files(
        [
            (
                f"src/teamster/{CODE_LOCATION}/powerschool/db/config/"
                "assets-transactiondate.yaml"
            )
        ]
    )["assets"]
]

ps_assignment_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-assignment.yaml"]
    )["assets"]
]

ps_contacts_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-contacts.yaml"]
    )["assets"]
]

ps_custom_assets = [
    table_asset_factory(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=POWERSCHOOL_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-custom.yaml"]
    )["assets"]
]
