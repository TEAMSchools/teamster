{{
    teamster_utils.generate_staging_model(
        unique_key="studentsdcid.int_value",
        transform_cols=[
            {"name": "studentsdcid", "extract": "int_value"},
            {"name": "c_504_status", "cast": "int"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

select *, if(c_504_status = 1, true, false) as is_504
from staging
