{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="id",
        transform_cols=[
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "studentsdcid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
