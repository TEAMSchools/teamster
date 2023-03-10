{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="phonenumberid",
        transform_cols=[
            {
                "name": "phonenumberid",
                "extract": "int_value",
            },
            {"name": "issms", "extract": "int_value"},
        ],
    )
}}
