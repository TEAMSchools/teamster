{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "studentid", "transformation": "extract", "type": "int_value"},
            {"name": "sectionid", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "termid", "transformation": "extract", "type": "int_value"},
            {
                "name": "attendance_type_code",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "unused2", "transformation": "extract", "type": "int_value"},
            {
                "name": "currentabsences",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "currenttardies",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "teacherid", "transformation": "extract", "type": "int_value"},
            {
                "name": "origsectionid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "unused3", "transformation": "extract", "type": "int_value"},
            {"name": "studyear", "transformation": "extract", "type": "int_value"},
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
