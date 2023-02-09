{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="assignmentscoreid",
        transform_cols=[
            {"name": "assignmentscoreid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "assignmentsectionid", "type": "int_value"},
            {"name": "studentsdcid", "type": "int_value"},
            {"name": "islate", "type": "int_value"},
            {"name": "iscollected", "type": "int_value"},
            {"name": "isexempt", "type": "int_value"},
            {"name": "ismissing", "type": "int_value"},
            {"name": "isabsent", "type": "int_value"},
            {"name": "isincomplete", "type": "int_value"},
            {"name": "actualscoregradescaledcid", "type": "int_value"},
            {"name": "scorepercent", "type": "bytes_decimal_value"},
            {"name": "scorepoints", "type": "bytes_decimal_value"},
            {"name": "scorenumericgrade", "type": "bytes_decimal_value"},
            {"name": "scoregradescaledcid", "type": "int_value"},
            {"name": "altnumericgrade", "type": "bytes_decimal_value"},
            {"name": "altscoregradescaledcid", "type": "int_value"},
            {"name": "hasretake", "type": "int_value"},
            {"name": "authoredbyuc", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
