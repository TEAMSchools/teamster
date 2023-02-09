{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location="powerschool",
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="gradecalcschoolassocid",
        transform_cols=[
            {"name": "gradecalcschoolassocid", "type": "int_value"},
            {"name": "gradecalculationtypeid", "type": "int_value"},
            {"name": "schoolsdcid", "type": "int_value"},
        ],
    )
}}
