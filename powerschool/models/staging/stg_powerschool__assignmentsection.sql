{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="assignmentsectionid",
        transform_cols=[
            {"name": "assignmentsectionid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "sectionsdcid", "type": "int_value"},
            {"name": "assignmentid", "type": "int_value"},
            {"name": "relatedgradescaleitemdcid", "type": "int_value"},
            {"name": "scoreentrypoints", "type": "bytes_decimal_value"},
            {"name": "extracreditpoints", "type": "bytes_decimal_value"},
            {"name": "weight", "type": "bytes_decimal_value"},
            {"name": "totalpointvalue", "type": "bytes_decimal_value"},
            {"name": "iscountedinfinalgrade", "type": "int_value"},
            {"name": "isscoringneeded", "type": "int_value"},
            {"name": "publishdaysbeforedue", "type": "int_value"},
            {"name": "publishedscoretypeid", "type": "int_value"},
            {"name": "isscorespublish", "type": "int_value"},
            {"name": "maxretakeallowed", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
