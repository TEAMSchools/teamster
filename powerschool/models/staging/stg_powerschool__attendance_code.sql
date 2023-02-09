{{
    transform_cols_base_model(
        source(var("code_location"), this.identifier | replace("stg", "src")),
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "course_credit_points", "type": "double_value"},
            {"name": "assignment_filter_yn", "type": "int_value"},
            {"name": "calculate_ada_yn", "type": "int_value"},
            {"name": "calculate_adm_yn", "type": "int_value"},
            {"name": "sortorder", "type": "int_value"},
        ],
    )
}}
