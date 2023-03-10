{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personphonenumberassocid",
        transform_cols=[
            {
                "name": "personphonenumberassocid",
                "extract": "int_value",
            },
            {"name": "personid", "extract": "int_value"},
            {
                "name": "phonenumberid",
                "extract": "int_value",
            },
            {
                "name": "phonetypecodesetid",
                "extract": "int_value",
            },
            {
                "name": "phonenumberpriorityorder",
                "extract": "int_value",
            },
            {"name": "ispreferred", "extract": "int_value"},
        ],
    )
}}
