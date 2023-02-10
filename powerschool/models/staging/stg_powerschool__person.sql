{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "prefixcodesetid", "type": "int_value"},
            {"name": "suffixcodesetid", "type": "int_value"},
            {"name": "gendercodesetid", "type": "int_value"},
            {"name": "statecontactnumber", "type": "int_value"},
            {"name": "isactive", "type": "int_value"},
            {"name": "excludefromstatereporting", "type": "int_value"},
        ],
    )
}}
