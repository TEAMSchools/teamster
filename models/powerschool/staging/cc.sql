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
