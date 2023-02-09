{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
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
