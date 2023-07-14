{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "termid", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "creditpct", "extract": "double_value"},
            {"name": "collect", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "showonspreadsht", "extract": "int_value"},
            {"name": "currentgrade", "extract": "int_value"},
            {"name": "storegrades", "extract": "int_value"},
            {"name": "numattpoints", "extract": "double_value"},
            {"name": "suppressltrgrd", "extract": "int_value"},
            {"name": "gradescaleid", "extract": "int_value"},
            {"name": "suppresspercentscr", "extract": "int_value"},
            {"name": "aregradeslocked", "extract": "int_value"},
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
