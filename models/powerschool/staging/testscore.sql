{{
    transform_cols_base_model(
        source_name=model.fqn[1],
        model_name=this.identifier,
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "testid", "type": "int_value"},
            {"name": "sortorder", "type": "int_value"},
        ],
    )
}}
