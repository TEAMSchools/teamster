{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personaddressassocid",
        transform_cols=[
            {"name": "personaddressassocid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "personaddressid", "type": "int_value"},
            {"name": "addresstypecodesetid", "type": "int_value"},
            {"name": "addresspriorityorder", "type": "int_value"},
        ],
    )
}}
