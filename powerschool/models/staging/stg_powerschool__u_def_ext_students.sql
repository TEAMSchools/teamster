{{
    incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="studentsdcid",
        transform_cols=[
            {"name": "studentsdcid", "type": "int_value"},
            {"name": "savings_529_optin", "type": "int_value"},
            {"name": "iep_registration_followup", "type": "int_value"},
            {"name": "lep_registration_followup", "type": "int_value"},
            {"name": "test_field", "type": "int_value"},
            {"name": "current_programid", "type": "int_value"},
            {"name": "aup_yn_1718", "type": "int_value"},
            {"name": "incorrect_region_grad_student", "type": "int_value"},
        ],
    )
}}
