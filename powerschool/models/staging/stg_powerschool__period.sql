{{
    transform_cols_base_model(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "year_id", "type": "int_value"},
            {"name": "period_number", "type": "int_value"},
            {"name": "sort_order", "type": "int_value"},
        ],
    )
}}
