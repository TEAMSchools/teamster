{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "users_dcid", "extract": "int_value"},
            {"name": "balance1", "extract": "double_value"},
            {"name": "balance2", "extract": "double_value"},
            {"name": "balance3", "extract": "double_value"},
            {"name": "balance4", "extract": "double_value"},
            {"name": "noofcurclasses", "extract": "int_value"},
            {"name": "staffstatus", "extract": "int_value"},
            {"name": "status", "extract": "int_value"},
            {"name": "sched_maximumcourses", "extract": "int_value"},
            {"name": "sched_maximumduty", "extract": "int_value"},
            {"name": "sched_maximumfree", "extract": "int_value"},
            {"name": "sched_totalcourses", "extract": "int_value"},
            {"name": "sched_maximumconsecutive", "extract": "int_value"},
            {"name": "sched_isteacherfree", "extract": "int_value"},
            {"name": "sched_teachermoreoneschool", "extract": "int_value"},
            {"name": "sched_substitute", "extract": "int_value"},
            {"name": "sched_scheduled", "extract": "int_value"},
            {"name": "sched_usebuilding", "extract": "int_value"},
            {"name": "sched_usehouse", "extract": "int_value"},
            {"name": "sched_lunch", "extract": "int_value"},
            {"name": "sched_maxpers", "extract": "int_value"},
            {"name": "sched_maxpreps", "extract": "int_value"},
            {"name": "whomodifiedid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

select *
from staging
