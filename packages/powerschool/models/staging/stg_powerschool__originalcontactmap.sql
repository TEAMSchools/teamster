{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="originalcontactmapid",
        transform_cols=[
            {
                "name": "originalcontactmapid",
                "extract": "int_value",
            },
            {
                "name": "studentcontactassocid",
                "extract": "int_value",
            },
        ],
    )
}}
