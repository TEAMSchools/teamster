{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personphonenumberassocid",
        transform_cols=[
            {
                "name": "personphonenumberassocid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "personid", "transformation": "extract", "type": "int_value"},
            {
                "name": "phonenumberid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "phonetypecodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "phonenumberpriorityorder",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "ispreferred", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
