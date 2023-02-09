{{
    transform_cols_base_model(
        source(var("code_location"), this.identifier | replace("stg", "src")),
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "test_type", "type": "int_value"},
        ],
    )
}}
