{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "a", "transformation": "extract", "type": "int_value"},
            {"name": "b", "transformation": "extract", "type": "int_value"},
            {"name": "c", "transformation": "extract", "type": "int_value"},
            {"name": "d", "transformation": "extract", "type": "int_value"},
            {"name": "e", "transformation": "extract", "type": "int_value"},
            {"name": "f", "transformation": "extract", "type": "int_value"},
            {"name": "insession", "transformation": "extract", "type": "int_value"},
            {
                "name": "membershipvalue",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "cycle_day_id",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "bell_schedule_id",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "week_num", "transformation": "extract", "type": "int_value"},
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
