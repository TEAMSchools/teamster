{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "studentid", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "grade_level", "transformation": "extract", "type": "int_value"},
            {"name": "type", "transformation": "extract", "type": "int_value"},
            {
                "name": "enrollmentcode",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fulltimeequiv_obsolete",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "membershipshare",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "tuitionpayer",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "fteid", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
