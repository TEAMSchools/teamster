{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "programid", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "gradelevel", "transformation": "extract", "type": "int_value"},
            {"name": "studentid", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
