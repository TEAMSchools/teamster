{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="codesetid",
        transform_cols=[
            {"name": "codesetid", "type": "int_value"},
            {"name": "parentcodesetid", "type": "int_value"},
            {"name": "uidisplayorder", "type": "int_value"},
            {"name": "isvisible", "type": "int_value"},
            {"name": "ismodifiable", "type": "int_value"},
            {"name": "isdeletable", "type": "int_value"},
            {"name": "excludefromstatereporting", "type": "int_value"},
        ],
    )
}}
