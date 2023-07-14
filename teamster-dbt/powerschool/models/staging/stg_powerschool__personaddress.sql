{{
    teamster_utils.generate_staging_model(
        unique_key="personaddressid.int_value",
        transform_cols=[
            {"name": "personaddressid", "extract": "int_value"},
            {"name": "statescodesetid", "extract": "int_value"},
            {"name": "countrycodesetid", "extract": "int_value"},
            {"name": "geocodelatitude", "extract": "bytes_decimal_value"},
            {"name": "geocodelongitude", "extract": "bytes_decimal_value"},
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
