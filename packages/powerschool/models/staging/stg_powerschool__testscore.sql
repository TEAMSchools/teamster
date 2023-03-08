{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "testid", "transformation": "extract", "type": "int_value"},
            {"name": "sortorder", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
