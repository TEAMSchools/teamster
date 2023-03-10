{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "attendance_conversion_id", "extract": "int_value"},
            {"name": "input_value", "extract": "int_value"},
            {"name": "attendance_value", "extract": "double_value"},
            {"name": "fteid", "extract": "int_value"},
            {"name": "unused", "extract": "int_value"},
            {"name": "daypartid", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}
