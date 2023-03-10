{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "studentid", "extract": "int_value"},
            {"name": "sectionid", "extract": "int_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "termid", "extract": "int_value"},
            {
                "name": "attendance_type_code",
                "extract": "int_value",
            },
            {"name": "unused2", "extract": "int_value"},
            {
                "name": "currentabsences",
                "extract": "int_value",
            },
            {
                "name": "currenttardies",
                "extract": "int_value",
            },
            {"name": "teacherid", "extract": "int_value"},
            {
                "name": "origsectionid",
                "extract": "int_value",
            },
            {"name": "unused3", "extract": "int_value"},
            {"name": "studyear", "extract": "int_value"},
            {
                "name": "whomodifiedid",
                "extract": "int_value",
            },
        ],
    )
}}
