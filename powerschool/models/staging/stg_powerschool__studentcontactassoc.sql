{{
    teamster_utils.incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=teamster_utils.get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="studentcontactassocid",
        transform_cols=[
            {"name": "studentcontactassocid", "type": "int_value"},
            {"name": "studentdcid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "contactpriorityorder", "type": "int_value"},
            {"name": "currreltypecodesetid", "type": "int_value"},
        ],
    )
}}
