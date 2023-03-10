{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="id",
        transform_cols=[
            {"name": "id", "extract": "int_value"},
            {
                "name": "studentsdcid",
                "extract": "int_value",
            },
        ],
    )
}}
