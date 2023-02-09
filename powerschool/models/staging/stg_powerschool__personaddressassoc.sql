{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location="powerschool",
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
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
