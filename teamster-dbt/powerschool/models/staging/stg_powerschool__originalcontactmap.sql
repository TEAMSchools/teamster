{{
    teamster_utils.generate_staging_model(
        unique_key="originalcontactmapid.int_value",
        transform_cols=[
            {"name": "originalcontactmapid", "extract": "int_value"},
            {"name": "studentcontactassocid", "extract": "int_value"},
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
