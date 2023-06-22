{{
    teamster_utils.generate_staging_model(
        unique_key="id.int_value",
        transform_cols=[
            {"name": "id", "extract": "int_value"},
            {"name": "teacherid", "extract": "int_value"},
            {"name": "sectionid", "extract": "int_value"},
            {"name": "roleid", "extract": "int_value"},
            {"name": "allocation", "extract": "bytes_decimal_value"},
            {"name": "priorityorder", "extract": "int_value"},
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
