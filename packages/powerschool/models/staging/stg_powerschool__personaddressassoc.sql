{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="personaddressassocid",
        transform_cols=[
            {
                "name": "personaddressassocid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "personid", "transformation": "extract", "type": "int_value"},
            {
                "name": "personaddressid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "addresstypecodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "addresspriorityorder",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
