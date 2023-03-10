{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "year_id", "extract": "int_value"},
            {
                "name": "attendance_conversion_id",
                "extract": "int_value",
            },
        ],
    )
}}
