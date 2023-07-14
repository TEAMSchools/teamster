{{
    teamster_utils.generate_staging_model(
        unique_key="gradecalcformulaweightid.int_value",
        transform_cols=[
            {"name": "gradecalcformulaweightid", "extract": "int_value"},
            {"name": "gradecalculationtypeid", "extract": "int_value"},
            {"name": "teachercategoryid", "extract": "int_value"},
            {"name": "districtteachercategoryid", "extract": "int_value"},
            {"name": "assignmentid", "extract": "int_value"},
            {"name": "weight", "extract": "bytes_decimal_value"},
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
