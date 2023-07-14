{{
    teamster_utils.generate_staging_model(
        unique_key="gradeformulasetid.int_value",
        transform_cols=[
            {"name": "gradeformulasetid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "iscoursegradecalculated", "extract": "int_value"},
            {"name": "isreporttermsetupsame", "extract": "int_value"},
            {"name": "sectionsdcid", "extract": "int_value"},
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
