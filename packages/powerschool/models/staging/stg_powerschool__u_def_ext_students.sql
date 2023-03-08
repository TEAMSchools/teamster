{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="studentsdcid",
        transform_cols=[
            {
                "name": "studentsdcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "savings_529_optin",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iep_registration_followup",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "lep_registration_followup",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "test_field", "transformation": "extract", "type": "int_value"},
            {
                "name": "current_programid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "aup_yn_1718", "transformation": "extract", "type": "int_value"},
            {
                "name": "incorrect_region_grad_student",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
