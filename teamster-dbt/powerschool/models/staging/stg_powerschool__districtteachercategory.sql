{{
    teamster_utils.generate_staging_model(
        unique_key="districtteachercategoryid.int_value",
        transform_cols=[
            {"name": "districtteachercategoryid", "extract": "int_value"},
            {"name": "isinfinalgrades", "extract": "int_value"},
            {"name": "isactive", "extract": "int_value"},
            {"name": "isusermodifiable", "extract": "int_value"},
            {"name": "displayposition", "extract": "int_value"},
            {"name": "defaultscoreentrypoints", "extract": "bytes_decimal_value"},
            {"name": "defaultextracreditpoints", "extract": "bytes_decimal_value"},
            {"name": "defaultweight", "extract": "bytes_decimal_value"},
            {"name": "defaulttotalvalue", "extract": "bytes_decimal_value"},
            {"name": "isdefaultpublishscores", "extract": "int_value"},
            {"name": "defaultdaysbeforedue", "extract": "int_value"},
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
