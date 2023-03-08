{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "attendance_conversion_id",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "input_value", "transformation": "extract", "type": "int_value"},
            {
                "name": "attendance_value",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "fteid", "transformation": "extract", "type": "int_value"},
            {"name": "unused", "transformation": "extract", "type": "int_value"},
            {"name": "daypartid", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
