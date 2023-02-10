{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "studentid", "type": "int_value"},
            {"name": "sectionid", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "termid", "type": "int_value"},
            {"name": "attendance_type_code", "type": "int_value"},
            {"name": "unused2", "type": "int_value"},
            {"name": "currentabsences", "type": "int_value"},
            {"name": "currenttardies", "type": "int_value"},
            {"name": "teacherid", "type": "int_value"},
            {"name": "origsectionid", "type": "int_value"},
            {"name": "unused3", "type": "int_value"},
            {"name": "studyear", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
