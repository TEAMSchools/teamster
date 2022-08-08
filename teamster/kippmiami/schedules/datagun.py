import os

from dagster import ScheduleDefinition, config_from_files

from teamster.kippmiami.jobs.datagun import datagun_etl_sftp

LOCAL_TIME_ZONE = os.getenv("LOCAL_TIME_ZONE")

powerschool_datagun = ScheduleDefinition(
    name="powerschool_datagun_mia",
    job=datagun_etl_sftp,
    cron_schedule="15 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/local/config/datagun/query-powerschool.yaml",
        ]
    ),
)

__all__ = [
    "powerschool_datagun",
]
