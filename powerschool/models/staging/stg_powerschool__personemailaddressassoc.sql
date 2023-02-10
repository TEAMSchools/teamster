{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personemailaddressassocid",
        transform_cols=[
            {"name": "personemailaddressassocid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "emailaddressid", "type": "int_value"},
            {"name": "emailtypecodesetid", "type": "int_value"},
            {"name": "isprimaryemailaddress", "type": "int_value"},
            {"name": "emailaddresspriorityorder", "type": "int_value"},
        ],
    )
}}
