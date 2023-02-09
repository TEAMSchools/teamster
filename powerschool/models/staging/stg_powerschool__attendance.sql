{{
    teamster_utils.incremental_merge_source_file(
        from_source=source("powerschool", this.identifier | replace("stg", "src")),
        file_uri=teamster_utils.get_gcs_uri(
            code_location=var("code_location"),
            system_name="powerschool",
            model_name=this.identifier | replace("stg_powerschool__", ""),
            partition_path=var("partition_path"),
        ),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "attendance_codeid", "type": "int_value"},
            {"name": "calendar_dayid", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "studentid", "type": "int_value"},
            {"name": "ccid", "type": "int_value"},
            {"name": "periodid", "type": "int_value"},
            {"name": "parent_attendanceid", "type": "int_value"},
            {"name": "att_interval", "type": "int_value"},
            {"name": "lock_teacher_yn", "type": "int_value"},
            {"name": "lock_reporting_yn", "type": "int_value"},
            {"name": "total_minutes", "type": "int_value"},
            {"name": "ada_value_code", "type": "double_value"},
            {"name": "ada_value_time", "type": "double_value"},
            {"name": "adm_value", "type": "double_value"},
            {"name": "programid", "type": "int_value"},
            {"name": "att_flags", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
