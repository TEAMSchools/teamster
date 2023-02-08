{%- set code_location = "kippcamden" -%}

{%- set source_name = model.fqn[1] -%}
{%- set model_name = this.identifier -%}

{{
    incremental_merge_source_file(
        source_name=source_name,
        model_name=model_name,
        file_uri=get_gcs_uri(
            code_location, source_name, model_name, var("partition_path")
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
            {"name": "ada_value_code", "type": "int_value"},
            {"name": "ada_value_time", "type": "int_value"},
            {"name": "adm_value", "type": "int_value"},
            {"name": "programid", "type": "int_value"},
            {"name": "att_flags", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
