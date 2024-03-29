{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "attendance_codeid", "extract": "int_value"},
            {"name": "calendar_dayid", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "ccid", "extract": "int_value"},
            {"name": "periodid", "extract": "int_value"},
            {"name": "parent_attendanceid", "extract": "int_value"},
            {"name": "att_interval", "extract": "int_value"},
            {"name": "lock_teacher_yn", "extract": "int_value"},
            {"name": "lock_reporting_yn", "extract": "int_value"},
            {"name": "total_minutes", "extract": "int_value"},
            {"name": "ada_value_code", "extract": "double_value"},
            {"name": "ada_value_time", "extract": "double_value"},
            {"name": "adm_value", "extract": "double_value"},
            {"name": "programid", "extract": "int_value"},
            {"name": "att_flags", "extract": "int_value"},
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
