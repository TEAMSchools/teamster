{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
            {
                "name": "course_credit_points",
                "extract": "double_value",
            },
            {
                "name": "assignment_filter_yn",
                "extract": "int_value",
            },
            {
                "name": "calculate_ada_yn",
                "extract": "int_value",
            },
            {
                "name": "calculate_adm_yn",
                "extract": "int_value",
            },
            {"name": "sortorder", "extract": "int_value"},
        ],
    )
}}
