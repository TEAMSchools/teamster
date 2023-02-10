{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="codesetid",
        transform_cols=[
            {"name": "codesetid", "type": "int_value"},
            {"name": "parentcodesetid", "type": "int_value"},
            {"name": "uidisplayorder", "type": "int_value"},
            {"name": "isvisible", "type": "int_value"},
            {"name": "ismodifiable", "type": "int_value"},
            {"name": "isdeletable", "type": "int_value"},
            {"name": "excludefromstatereporting", "type": "int_value"},
        ],
    )
}}
