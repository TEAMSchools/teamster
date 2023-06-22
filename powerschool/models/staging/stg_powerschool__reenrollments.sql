{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "grade_level", "extract": "int_value"},
            {"name": "type", "extract": "int_value"},
            {"name": "enrollmentcode", "extract": "int_value"},
            {"name": "fulltimeequiv_obsolete", "extract": "double_value"},
            {"name": "membershipshare", "extract": "double_value"},
            {"name": "tuitionpayer", "extract": "int_value"},
            {"name": "fteid", "extract": "int_value"},
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
