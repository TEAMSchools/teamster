{{
    teamster_utils.generate_staging_model(
        unique_key="id.int_value",
        transform_cols=[
            {"name": "id", "extract": "int_value"},
            {"name": "rolemoduleid", "extract": "int_value"},
            {"name": "islocked", "extract": "int_value"},
            {"name": "isvisible", "extract": "int_value"},
            {"name": "isenabled", "extract": "int_value"},
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
