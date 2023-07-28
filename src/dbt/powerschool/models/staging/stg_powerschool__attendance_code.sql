{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "course_credit_points", "extract": "double_value"},
            {"name": "assignment_filter_yn", "extract": "int_value"},
            {"name": "calculate_ada_yn", "extract": "int_value"},
            {"name": "calculate_adm_yn", "extract": "int_value"},
            {"name": "sortorder", "extract": "int_value"},
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
