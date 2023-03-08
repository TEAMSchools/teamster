{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "prefixcodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "suffixcodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gendercodesetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "statecontactnumber",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isactive", "transformation": "extract", "type": "int_value"},
            {
                "name": "excludefromstatereporting",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
