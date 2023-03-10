{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "grade_level", "extract": "int_value"},
            {"name": "type", "extract": "int_value"},
            {
                "name": "enrollmentcode",
                "extract": "int_value",
            },
            {
                "name": "fulltimeequiv_obsolete",
                "extract": "double_value",
            },
            {
                "name": "membershipshare",
                "extract": "double_value",
            },
            {
                "name": "tuitionpayer",
                "extract": "int_value",
            },
            {"name": "fteid", "extract": "int_value"},
        ],
    )
}}
