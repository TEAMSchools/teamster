{{
    teamster_utils.incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=teamster_utils.get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="phonenumberid",
        transform_cols=[
            {"name": "phonenumberid", "type": "int_value"},
            {"name": "issms", "type": "int_value"},
        ],
    )
}}
