{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personemailaddressassocid",
        transform_cols=[
            {
                "name": "personemailaddressassocid",
                "extract": "int_value",
            },
            {"name": "personid", "extract": "int_value"},
            {
                "name": "emailaddressid",
                "extract": "int_value",
            },
            {
                "name": "emailtypecodesetid",
                "extract": "int_value",
            },
            {
                "name": "isprimaryemailaddress",
                "extract": "int_value",
            },
            {
                "name": "emailaddresspriorityorder",
                "extract": "int_value",
            },
        ],
    )
}}
