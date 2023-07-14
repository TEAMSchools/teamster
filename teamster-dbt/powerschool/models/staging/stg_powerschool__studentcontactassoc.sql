{{
    teamster_utils.generate_staging_model(
        unique_key="studentcontactassocid.int_value",
        transform_cols=[
            {"name": "studentcontactassocid", "extract": "int_value"},
            {"name": "studentdcid", "extract": "int_value"},
            {"name": "personid", "extract": "int_value"},
            {"name": "contactpriorityorder", "extract": "int_value"},
            {"name": "currreltypecodesetid", "extract": "int_value"},
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
