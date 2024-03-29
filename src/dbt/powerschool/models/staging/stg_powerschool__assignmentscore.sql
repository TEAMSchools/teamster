{{
    teamster_utils.generate_staging_model(
        unique_key="assignmentscoreid.int_value",
        transform_cols=[
            {"name": "assignmentscoreid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "assignmentsectionid", "extract": "int_value"},
            {"name": "studentsdcid", "extract": "int_value"},
            {"name": "islate", "extract": "int_value"},
            {"name": "iscollected", "extract": "int_value"},
            {"name": "isexempt", "extract": "int_value"},
            {"name": "ismissing", "extract": "int_value"},
            {"name": "isabsent", "extract": "int_value"},
            {"name": "isincomplete", "extract": "int_value"},
            {"name": "actualscoregradescaledcid", "extract": "int_value"},
            {"name": "scorepercent", "extract": "bytes_decimal_value"},
            {"name": "scorepoints", "extract": "bytes_decimal_value"},
            {"name": "scorenumericgrade", "extract": "bytes_decimal_value"},
            {"name": "scoregradescaledcid", "extract": "int_value"},
            {"name": "altnumericgrade", "extract": "bytes_decimal_value"},
            {"name": "altscoregradescaledcid", "extract": "int_value"},
            {"name": "hasretake", "extract": "int_value"},
            {"name": "authoredbyuc", "extract": "int_value"},
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
