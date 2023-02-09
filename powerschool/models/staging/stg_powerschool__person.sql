{{
    incremental_merge_source_file(
        source(var("code_location"), this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
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
