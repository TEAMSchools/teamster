{{
    teamster_utils.generate_staging_model(
        unique_key="assignmentcategoryassocid.int_value",
        transform_cols=[
            {"name": "assignmentcategoryassocid", "extract": "int_value"},
            {"name": "assignmentsectionid", "extract": "int_value"},
            {"name": "teachercategoryid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {"name": "isprimary", "extract": "int_value"},
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
