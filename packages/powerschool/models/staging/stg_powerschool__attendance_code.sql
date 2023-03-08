{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {
                "name": "course_credit_points",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "assignment_filter_yn",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "calculate_ada_yn",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "calculate_adm_yn",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "sortorder", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
