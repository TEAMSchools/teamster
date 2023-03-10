{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "programid", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "gradelevel", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
        ],
    )
}}
