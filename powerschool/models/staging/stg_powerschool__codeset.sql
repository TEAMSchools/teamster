{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="codesetid",
        transform_cols=[
            {"name": "codesetid", "transformation": "extract", "type": "int_value"},
            {
                "name": "parentcodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "uidisplayorder",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isvisible", "transformation": "extract", "type": "int_value"},
            {
                "name": "ismodifiable",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isdeletable", "transformation": "extract", "type": "int_value"},
            {
                "name": "excludefromstatereporting",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
