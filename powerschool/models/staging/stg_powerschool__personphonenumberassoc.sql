{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personphonenumberassocid",
        transform_cols=[
            {"name": "personphonenumberassocid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "phonenumberid", "type": "int_value"},
            {"name": "phonetypecodesetid", "type": "int_value"},
            {"name": "phonenumberpriorityorder", "type": "int_value"},
            {"name": "ispreferred", "type": "int_value"},
        ],
    )
}}
