{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "year_id", "transformation": "extract", "type": "int_value"},
            {
                "name": "period_number",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "sort_order", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
