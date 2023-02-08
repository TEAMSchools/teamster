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
        unique_key="codesetid",
        transform_cols=[
            {"name": "codesetid", "type": "int_value"},
            {"name": "parentcodesetid", "type": "int_value"},
            {"name": "uidisplayorder", "type": "int_value"},
            {"name": "isvisible", "type": "int_value"},
            {"name": "ismodifiable", "type": "int_value"},
            {"name": "isdeletable", "type": "int_value"},
            {"name": "excludefromstatereporting", "type": "int_value"},
        ],
    )
}}
