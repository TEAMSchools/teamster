{{
    teamster_utils.generate_staging_model(
        unique_key="coursesdcid.int_value",
        transform_cols=[
            {"name": "coursesdcid", "extract": "int_value"},
            {"name": "exclude_course_submission_tf", "extract": "int_value"},
            {"name": "sla_include_tf", "extract": "int_value"},
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
