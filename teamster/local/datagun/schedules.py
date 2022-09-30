import os

from dagster import ScheduleDefinition, config_from_files

# from teamster.core.datagun.jobs import datagun_etl_sftp

LOCAL_TIME_ZONE = os.getenv("LOCAL_TIME_ZONE")

# powerschool_datagun = ScheduleDefinition(
#     name="powerschool_datagun_nwk",
#     job=datagun_etl_sftp,
#     cron_schedule="15 2 * * *",
#     execution_timezone=LOCAL_TIME_ZONE,
#     run_config=config_from_files(
#         [
#             "./teamster/core/resources/config/google.yaml",
#             "./teamster/core/datagun/config/resource.yaml",
#             "./teamster/local/datagun/config/query-powerschool.yaml",
#         ]
#     ),
# )

# nps_datagun = ScheduleDefinition(
#     name="nps_datagun",
#     job=datagun_etl_sftp,
#     cron_schedule="0 0 * * *",
#     execution_timezone=LOCAL_TIME_ZONE,
#     run_config=config_from_files(
#         [
#             "./teamster/core/resources/config/google.yaml",
#             "./teamster/core/datagun/config/resource.yaml",
#             "./teamster/local/datagun/config/query-nps.yaml",
#         ]
#     ),
# )

# __all__ = [
#     "powerschool_datagun",
#     "nps_datagun",
# ]
