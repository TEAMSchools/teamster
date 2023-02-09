{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location="powerschool",
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "studentid", "type": "int_value"},
            {"name": "sectionid", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "termid", "type": "int_value"},
            {"name": "attendance_type_code", "type": "int_value"},
            {"name": "unused2", "type": "int_value"},
            {"name": "currentabsences", "type": "int_value"},
            {"name": "currenttardies", "type": "int_value"},
            {"name": "teacherid", "type": "int_value"},
            {"name": "origsectionid", "type": "int_value"},
            {"name": "unused3", "type": "int_value"},
            {"name": "studyear", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
