{{
    transform_cols_base_model(
        source(var("code_location"), this.identifier | replace("stg", "src")),
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "a", "type": "int_value"},
            {"name": "b", "type": "int_value"},
            {"name": "c", "type": "int_value"},
            {"name": "d", "type": "int_value"},
            {"name": "e", "type": "int_value"},
            {"name": "f", "type": "int_value"},
            {"name": "insession", "type": "int_value"},
            {"name": "membershipvalue", "type": "double_value"},
            {"name": "cycle_day_id", "type": "int_value"},
            {"name": "bell_schedule_id", "type": "int_value"},
            {"name": "week_num", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
