{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "a", "extract": "int_value"},
            {"name": "b", "extract": "int_value"},
            {"name": "c", "extract": "int_value"},
            {"name": "d", "extract": "int_value"},
            {"name": "e", "extract": "int_value"},
            {"name": "f", "extract": "int_value"},
            {"name": "insession", "extract": "int_value"},
            {"name": "membershipvalue", "extract": "double_value"},
            {"name": "cycle_day_id", "extract": "int_value"},
            {"name": "bell_schedule_id", "extract": "int_value"},
            {"name": "week_num", "extract": "int_value"},
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
