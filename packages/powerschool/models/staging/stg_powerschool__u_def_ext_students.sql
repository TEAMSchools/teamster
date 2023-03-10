{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="studentsdcid",
        transform_cols=[
            {
                "name": "studentsdcid",
                "extract": "int_value",
            },
            {
                "name": "savings_529_optin",
                "extract": "int_value",
            },
            {
                "name": "iep_registration_followup",
                "extract": "int_value",
            },
            {
                "name": "lep_registration_followup",
                "extract": "int_value",
            },
            {"name": "test_field", "extract": "int_value"},
            {
                "name": "current_programid",
                "extract": "int_value",
            },
            {"name": "aup_yn_1718", "extract": "int_value"},
            {
                "name": "incorrect_region_grad_student",
                "extract": "int_value",
            },
        ],
    )
}}
