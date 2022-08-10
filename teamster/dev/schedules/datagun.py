import os

from dagster import ScheduleDefinition, config_from_files

from teamster.dev.jobs.datagun import datagun_etl_gsheets, datagun_etl_sftp

LOCAL_TIME_ZONE = os.getenv("LOCAL_TIME_ZONE")

deanslist_datagun = ScheduleDefinition(
    name="deanslist_datagun",
    job=datagun_etl_sftp,
    cron_schedule="25 1 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-deanslist.yaml",
        ]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "2000m", "memory": "2560Mi"}}
            }
        }
    },
)

illuminate_datagun = ScheduleDefinition(
    name="illuminate_datagun",
    job=datagun_etl_sftp,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-illuminate.yaml",
        ]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "1250m", "memory": "1536Mi"}}
            }
        }
    },
)

gsheets_datagun = ScheduleDefinition(
    name="gsheets_datagun",
    job=datagun_etl_gsheets,
    cron_schedule="0 6 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-gsheets.yaml",
        ]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "1250m", "memory": "1536Mi"}}
            }
        }
    },
)

clever_datagun = ScheduleDefinition(
    name="clever_datagun",
    job=datagun_etl_sftp,
    cron_schedule="@hourly",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-clever.yaml",
        ]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "1000m", "memory": "1536Mi"}}
            }
        }
    },
)

razkids_datagun = ScheduleDefinition(
    name="razkids_datagun",
    job=datagun_etl_sftp,
    cron_schedule="45 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-razkids.yaml",
        ]
    ),
)

read180_datagun = ScheduleDefinition(
    name="read180_datagun",
    job=datagun_etl_sftp,
    cron_schedule="	15 3 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-read180.yaml",
        ]
    ),
)

littlesis_datagun = ScheduleDefinition(
    name="littlesis_datagun",
    job=datagun_etl_sftp,
    cron_schedule="30 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-littlesis.yaml",
        ]
    ),
)

gam_datagun = ScheduleDefinition(
    name="gam_datagun",
    job=datagun_etl_sftp,
    cron_schedule="0 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-gam.yaml",
        ]
    ),
)

blissbook_datagun = ScheduleDefinition(
    name="blissbook_datagun",
    job=datagun_etl_sftp,
    cron_schedule="10 5 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-blissbook.yaml",
        ]
    ),
)

coupa_datagun = ScheduleDefinition(
    name="coupa_datagun",
    job=datagun_etl_sftp,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-coupa.yaml",
        ]
    ),
)

egencia_datagun = ScheduleDefinition(
    name="egencia_datagun",
    job=datagun_etl_sftp,
    cron_schedule="20 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-egencia.yaml",
        ]
    ),
)

adp_datagun = ScheduleDefinition(
    name="adp_datagun",
    job=datagun_etl_sftp,
    cron_schedule="10 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-adp.yaml",
        ]
    ),
)

fpodms_datagun = ScheduleDefinition(
    name="fpodms_datagun",
    job=datagun_etl_sftp,
    cron_schedule="40 2 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-fpodms.yaml",
        ]
    ),
)

njdoe_datagun = ScheduleDefinition(
    name="njdoe_datagun",
    job=datagun_etl_sftp,
    cron_schedule="55 11 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-njdoe.yaml",
        ]
    ),
)

whetstone_datagun = ScheduleDefinition(
    name="whetstone_datagun",
    job=datagun_etl_sftp,
    cron_schedule="55 3 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-whetstone.yaml",
        ]
    ),
)

idauto_datagun = ScheduleDefinition(
    name="idauto_datagun",
    job=datagun_etl_sftp,
    cron_schedule="55 * * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        [
            "./teamster/common/config/datagun/resource.yaml",
            "./teamster/common/config/google/resource.yaml",
            "./teamster/dev/config/datagun/query-idauto.yaml",
        ]
    ),
)

__all__ = [
    "deanslist_datagun",
    "illuminate_datagun",
    "gsheets_datagun",
    "clever_datagun",
    "razkids_datagun",
    "read180_datagun",
    "littlesis_datagun",
    "gam_datagun",
    "blissbook_datagun",
    "coupa_datagun",
    "egencia_datagun",
    "adp_datagun",
    "fpodms_datagun",
    "njdoe_datagun",
    "whetstone_datagun",
    "idauto_datagun",
]
