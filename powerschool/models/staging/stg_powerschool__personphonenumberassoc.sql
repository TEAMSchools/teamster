{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location="powerschool",
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="personphonenumberassocid",
        transform_cols=[
            {"name": "personphonenumberassocid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "phonenumberid", "type": "int_value"},
            {"name": "phonetypecodesetid", "type": "int_value"},
            {"name": "phonenumberpriorityorder", "type": "int_value"},
            {"name": "ispreferred", "type": "int_value"},
        ],
    )
}}
