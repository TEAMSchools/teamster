{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="usersdcid",
        transform_cols=[
            {"name": "usersdcid", "transformation": "extract", "type": "int_value"},
            {
                "name": "smart_salary",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "smart_yearsinlea",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "smart_yearsinnj",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "smart_yearsofexp",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excl_frm_smart_stf_submissn",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "smart_stafcompenanualsup",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "smart_stafcompnsatnbassal",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
