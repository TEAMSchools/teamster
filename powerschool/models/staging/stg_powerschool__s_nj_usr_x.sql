{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="usersdcid",
        transform_cols=[
            {"name": "usersdcid", "type": "int_value"},
            {"name": "smart_salary", "type": "int_value"},
            {"name": "smart_yearsinlea", "type": "int_value"},
            {"name": "smart_yearsinnj", "type": "int_value"},
            {"name": "smart_yearsofexp", "type": "int_value"},
            {"name": "excl_frm_smart_stf_submissn", "type": "int_value"},
            {"name": "smart_stafcompenanualsup", "type": "int_value"},
            {"name": "smart_stafcompnsatnbassal", "type": "int_value"},
        ],
    )
}}
