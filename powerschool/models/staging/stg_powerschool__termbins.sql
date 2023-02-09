{{
    teamster_utils.incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=teamster_utils.get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "termid", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "creditpct", "type": "double_value"},
            {"name": "collect", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "showonspreadsht", "type": "int_value"},
            {"name": "currentgrade", "type": "int_value"},
            {"name": "storegrades", "type": "int_value"},
            {"name": "numattpoints", "type": "double_value"},
            {"name": "suppressltrgrd", "type": "int_value"},
            {"name": "gradescaleid", "type": "int_value"},
            {"name": "suppresspercentscr", "type": "int_value"},
            {"name": "aregradeslocked", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
