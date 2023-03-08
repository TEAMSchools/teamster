{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {"name": "noofdays", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {
                "name": "yearlycredithrs",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "termsinyear", "transformation": "extract", "type": "int_value"},
            {"name": "portion", "transformation": "extract", "type": "int_value"},
            {
                "name": "autobuildbin",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isyearrec", "transformation": "extract", "type": "int_value"},
            {
                "name": "periods_per_day",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "days_per_cycle",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "attendance_calculation_code",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "sterms", "transformation": "extract", "type": "int_value"},
            {
                "name": "suppresspublicview",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
