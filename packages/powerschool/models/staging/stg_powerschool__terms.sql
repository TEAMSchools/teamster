{{
    incremental_merge_source_file(
        source(var("code_location"), this.identifier | replace("stg", "src")),
        file_uri=get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "noofdays", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "yearlycredithrs", "type": "double_value"},
            {"name": "termsinyear", "type": "int_value"},
            {"name": "portion", "type": "int_value"},
            {"name": "autobuildbin", "type": "int_value"},
            {"name": "isyearrec", "type": "int_value"},
            {"name": "periods_per_day", "type": "int_value"},
            {"name": "days_per_cycle", "type": "int_value"},
            {"name": "attendance_calculation_code", "type": "int_value"},
            {"name": "sterms", "type": "int_value"},
            {"name": "suppresspublicview", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
