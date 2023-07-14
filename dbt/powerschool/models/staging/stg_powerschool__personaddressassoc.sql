{{
    teamster_utils.generate_staging_model(
        unique_key="personaddressassocid.int_value",
        transform_cols=[
            {"name": "personaddressassocid", "extract": "int_value"},
            {"name": "personid", "extract": "int_value"},
            {"name": "personaddressid", "extract": "int_value"},
            {"name": "addresstypecodesetid", "extract": "int_value"},
            {"name": "addresspriorityorder", "extract": "int_value"},
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
