{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personemailaddressassocid",
        transform_cols=[
            {
                "name": "personemailaddressassocid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "personid", "transformation": "extract", "type": "int_value"},
            {
                "name": "emailaddressid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "emailtypecodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isprimaryemailaddress",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "emailaddresspriorityorder",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
