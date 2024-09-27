{{
    teamster_utils.generate_staging_model(
        unique_key="gradeschoolformulaassocid.int_value",
        transform_cols=[
            {"name": "gradeschoolformulaassocid", "extract": "int_value"},
            {"name": "gradeformulasetid", "extract": "int_value"},
            {"name": "gradeschoolconfigid", "extract": "int_value"},
            {"name": "isdefaultformulaset", "extract": "int_value"},
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
