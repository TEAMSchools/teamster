{{
    teamster_utils.incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=teamster_utils.get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="id",
        transform_cols=[
            {"name": "id", "type": "int_value"},
            {"name": "teacherid", "type": "int_value"},
            {"name": "sectionid", "type": "int_value"},
            {"name": "roleid", "type": "int_value"},
            {"name": "allocation", "type": "bytes_decimal_value"},
            {"name": "priorityorder", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
