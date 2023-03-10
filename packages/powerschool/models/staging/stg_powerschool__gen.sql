{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "valueli", "extract": "int_value"},
            {"name": "valueli2", "extract": "int_value"},
            {"name": "valuer", "extract": "double_value"},
            {"name": "sortorder", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "valueli3", "extract": "int_value"},
            {"name": "valuer2", "extract": "double_value"},
            {"name": "time1", "extract": "int_value"},
            {"name": "time2", "extract": "int_value"},
            {"name": "spedindicator", "extract": "int_value"},
            {"name": "valueli4", "extract": "int_value"},
            {"name": "yearid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}
