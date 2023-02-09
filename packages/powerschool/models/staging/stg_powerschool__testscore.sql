{{
    transform_cols_base_model(
        source(var("code_location"), this.identifier | replace("stg", "src")),
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "testid", "type": "int_value"},
            {"name": "sortorder", "type": "int_value"},
        ],
    )
}}
