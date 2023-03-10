{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="studentcontactassocid",
        transform_cols=[
            {
                "name": "studentcontactassocid",
                "extract": "int_value",
            },
            {"name": "studentdcid", "extract": "int_value"},
            {"name": "personid", "extract": "int_value"},
            {
                "name": "contactpriorityorder",
                "extract": "int_value",
            },
            {
                "name": "currreltypecodesetid",
                "extract": "int_value",
            },
        ],
    )
}}
