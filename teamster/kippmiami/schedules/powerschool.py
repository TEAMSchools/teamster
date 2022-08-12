import os

from dagster import ScheduleDefinition, config_from_files

from teamster.kippmiami.jobs.powerschool.api import powerschool_api_extract

LOCAL_TIME_ZONE = os.getenv("LOCAL_TIME_ZONE")

full_tables = ScheduleDefinition(
    name="full_tables",
    job=powerschool_api_extract,
    cron_schedule="0 * * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        ["./teamster/kippmiami/config/powerschool/query-full.yaml"]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "2500m", "memory": "3Gi"}}
            }
        }
    },
)

filtered_tables = ScheduleDefinition(
    name="filtered_tables",
    job=powerschool_api_extract,
    cron_schedule="5 * * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        ["./teamster/kippmiami/config/powerschool/query-filtered.yaml"]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "3000m", "memory": "3Gi"}}
            }
        }
    },
)

custom_tables = ScheduleDefinition(
    name="custom_tables",
    job=powerschool_api_extract,
    cron_schedule="10 * * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        ["./teamster/kippmiami/config/powerschool/query-custom.yaml"]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "1250m", "memory": "1.25Gi"}}
            }
        }
    },
)

contacts_tables = ScheduleDefinition(
    name="contacts_tables",
    job=powerschool_api_extract,
    cron_schedule="15 * * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        ["./teamster/kippmiami/config/powerschool/query-contacts.yaml"]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "1500m", "memory": "1.5Gi"}}
            }
        }
    },
)

attendance_tables = ScheduleDefinition(
    name="attendance_tables",
    job=powerschool_api_extract,
    cron_schedule="0 13 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        ["./teamster/kippmiami/config/powerschool/query-attendance.yaml"]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "7500m", "memory": "7.5Gi"}}
            }
        }
    },
)

assignment_tables = ScheduleDefinition(
    name="assignment_tables",
    job=powerschool_api_extract,
    cron_schedule="0 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        ["./teamster/kippmiami/config/powerschool/query-assignments.yaml"]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "2500m", "memory": "2.5Gi"}}
            }
        }
    },
)

assignmentscore = ScheduleDefinition(
    name="assignmentscore",
    job=powerschool_api_extract,
    cron_schedule="5 0 * * *",
    execution_timezone=LOCAL_TIME_ZONE,
    run_config=config_from_files(
        ["./teamster/kippmiami/config/powerschool/query-assignmentscore.yaml"]
    ),
    tags={
        "dagster-k8s/config": {
            "container_config": {
                "resources": {"limits": {"cpu": "3250m", "memory": "3.25Gi"}}
            }
        }
    },
)

__all__ = [
    "full_tables",
    "filtered_tables",
    "assignment_tables",
    "assignmentscore",
    "attendance_tables",
    "contacts_tables",
    "custom_tables",
]
