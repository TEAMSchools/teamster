{{
    teamster_utils.transform_cols_base_model(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "valueli", "type": "int_value"},
            {"name": "valueli2", "type": "int_value"},
            {"name": "valuer", "type": "double_value"},
            {"name": "sortorder", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "valueli3", "type": "int_value"},
            {"name": "valuer2", "type": "double_value"},
            {"name": "time1", "type": "int_value"},
            {"name": "time2", "type": "int_value"},
            {"name": "spedindicator", "type": "int_value"},
            {"name": "valueli4", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
        ],
    )
}}
