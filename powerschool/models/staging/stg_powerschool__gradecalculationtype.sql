{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="gradecalculationtypeid",
        transform_cols=[
            {"name": "gradecalculationtypeid", "type": "int_value"},
            {"name": "gradeformulasetid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "isnograde", "type": "int_value"},
            {"name": "isdroplowstudentfavor", "type": "int_value"},
            {"name": "isalternatepointsused", "type": "int_value"},
            {"name": "iscalcformulaeditable", "type": "int_value"},
            {"name": "isdropscoreeditable", "type": "int_value"},
        ],
    )
}}
