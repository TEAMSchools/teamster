{{
    teamster_utils.generate_staging_model(
        unique_key="gradecalculationtypeid.int_value",
        transform_cols=[
            {"name": "gradecalculationtypeid", "extract": "int_value"},
            {"name": "gradeformulasetid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "isnograde", "extract": "int_value"},
            {"name": "isdroplowstudentfavor", "extract": "int_value"},
            {"name": "isalternatepointsused", "extract": "int_value"},
            {"name": "iscalcformulaeditable", "extract": "int_value"},
            {"name": "isdropscoreeditable", "extract": "int_value"},
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
