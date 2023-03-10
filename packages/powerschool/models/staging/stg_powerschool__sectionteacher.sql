{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="id",
        transform_cols=[
            {"name": "id", "extract": "int_value"},
            {"name": "teacherid", "extract": "int_value"},
            {"name": "sectionid", "extract": "int_value"},
            {"name": "roleid", "extract": "int_value"},
            {
                "name": "allocation",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "priorityorder",
                "extract": "int_value",
            },
            {
                "name": "whomodifiedid",
                "extract": "int_value",
            },
        ],
    )
}}
