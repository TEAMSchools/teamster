{{
    teamster_utils.generate_staging_model(
        unique_key="DLRosterID, DLStudentID",
        transform_cols=[],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
            "_dagster_partition_school",
        ],
    )
}}

select *
from staging
