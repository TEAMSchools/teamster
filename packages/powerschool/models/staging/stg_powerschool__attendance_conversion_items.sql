{{
    transform_cols_base_model(
        source(var("code_location"), this.identifier | replace("stg", "src")),
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "attendance_conversion_id", "type": "int_value"},
            {"name": "input_value", "type": "int_value"},
            {"name": "attendance_value", "type": "double_value"},
            {"name": "fteid", "type": "int_value"},
            {"name": "unused", "type": "int_value"},
            {"name": "daypartid", "type": "int_value"},
        ],
    )
}}
