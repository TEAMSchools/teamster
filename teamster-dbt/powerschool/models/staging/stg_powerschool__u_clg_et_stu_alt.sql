{{
    teamster_utils.generate_staging_model(
        unique_key="id.int_value",
        transform_cols=[
            {"name": "id", "extract": "int_value"},
            {"name": "studentsdcid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

{{
    dbt_utils.deduplicate(
        relation="staging",
        partition_by="studentsdcid, exit_date",
        order_by="coalesce(whenmodified, whencreated) desc",
    )
}}
