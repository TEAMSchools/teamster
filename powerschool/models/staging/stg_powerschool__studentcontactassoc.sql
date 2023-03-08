{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="studentcontactassocid",
        transform_cols=[
            {
                "name": "studentcontactassocid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "studentdcid", "transformation": "extract", "type": "int_value"},
            {"name": "personid", "transformation": "extract", "type": "int_value"},
            {
                "name": "contactpriorityorder",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "currreltypecodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
