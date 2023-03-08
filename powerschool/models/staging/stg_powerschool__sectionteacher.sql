{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="id",
        transform_cols=[
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "teacherid", "transformation": "extract", "type": "int_value"},
            {"name": "sectionid", "transformation": "extract", "type": "int_value"},
            {"name": "roleid", "transformation": "extract", "type": "int_value"},
            {
                "name": "allocation",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "priorityorder",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
