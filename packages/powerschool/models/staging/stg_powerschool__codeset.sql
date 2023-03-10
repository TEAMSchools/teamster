{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="codesetid",
        transform_cols=[
            {"name": "codesetid", "extract": "int_value"},
            {"name": "parentcodesetid", "extract": "int_value"},
            {"name": "uidisplayorder", "extract": "int_value"},
            {"name": "isvisible", "extract": "int_value"},
            {"name": "ismodifiable", "extract": "int_value"},
            {"name": "isdeletable", "extract": "int_value"},
            {"name": "excludefromstatereporting", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}
