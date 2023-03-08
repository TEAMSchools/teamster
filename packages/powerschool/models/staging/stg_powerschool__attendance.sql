{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "attendance_codeid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "calendar_dayid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {"name": "studentid", "transformation": "extract", "type": "int_value"},
            {"name": "ccid", "transformation": "extract", "type": "int_value"},
            {"name": "periodid", "transformation": "extract", "type": "int_value"},
            {
                "name": "parent_attendanceid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "att_interval",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "lock_teacher_yn",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "lock_reporting_yn",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "total_minutes",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ada_value_code",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "ada_value_time",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "adm_value",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "programid", "transformation": "extract", "type": "int_value"},
            {"name": "att_flags", "transformation": "extract", "type": "int_value"},
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
