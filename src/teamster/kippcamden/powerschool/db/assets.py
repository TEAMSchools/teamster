from dagster import config_from_files

from teamster.core.powerschool.db.assets import build_powerschool_table_asset
from teamster.kippcamden import CODE_LOCATION, PS_PARTITION_START_DATE

# # TODO: rename to something like "full" or "non-partition"
# ps_daily_assets = [
#     build_powerschool_table_asset(**cfg, code_location=CODE_LOCATION)
#     for cfg in config_from_files(
#         [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-daily.yaml"]
#     )["assets"]
# ]

# ps_misc_assets = [
#     build_powerschool_table_asset(
#         **cfg, code_location=CODE_LOCATION, partition_start_date=PARTITION_START_DATE
#     )
#     for cfg in config_from_files(
#         [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-misc.yaml"]
#     )["assets"]
# ]

# ps_transactiondate_assets = [
#     build_powerschool_table_asset(
#         **cfg,
#         code_location=CODE_LOCATION,
#         partition_start_date=PARTITION_START_DATE,
#         where_column="transaction_date",
#     )
#     for cfg in config_from_files(
#         [
#             (
#                 f"src/teamster/{CODE_LOCATION}/powerschool/db/config/"
#                 "assets-transactiondate.yaml"
#             )
#         ]
#     )["assets"]
# ]

# ps_assignment_assets = [
#     build_powerschool_table_asset(
#         **cfg,
#         code_location=CODE_LOCATION,
#         partition_start_date=PARTITION_START_DATE,
#         where_column="whenmodified",
#     )
#     for cfg in config_from_files(
#         [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-assignment.yaml"]
#     )["assets"]
# ]

# ps_contacts_assets = [
#     build_powerschool_table_asset(
#         **cfg,
#         code_location=CODE_LOCATION,
#         partition_start_date=PARTITION_START_DATE,
#         where_column="whenmodified",
#     )
#     for cfg in config_from_files(
#         [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-contacts.yaml"]
#     )["assets"]
# ]

# ps_custom_assets = [
#     build_powerschool_table_asset(
#         **cfg,
#         code_location=CODE_LOCATION,
#         partition_start_date=PARTITION_START_DATE,
#         where_column="whenmodified",
#     )
#     for cfg in config_from_files(
#         [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-custom.yaml"]
#     )["assets"]
# ]

ps_test_assets = [
    build_powerschool_table_asset(
        **cfg,
        code_location=CODE_LOCATION,
        partition_start_date=PS_PARTITION_START_DATE,
        where_column="whenmodified",
    )
    for cfg in config_from_files(
        [f"src/teamster/{CODE_LOCATION}/powerschool/db/config/assets-test.yaml"]
    )["assets"]
]
