{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="id",
        transform_cols=[
            {"name": "id", "extract": "int_value"},
            {"name": "rolemoduleid", "extract": "int_value"},
            {"name": "islocked", "extract": "int_value"},
            {"name": "isvisible", "extract": "int_value"},
            {"name": "isenabled", "extract": "int_value"},
            {"name": "sortorder", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}
