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
        unique_key="coursesdcid",
        transform_cols=[
            {"name": "coursesdcid", "type": "int_value"},
            {"name": "exclude_course_submission_tf", "type": "int_value"},
            {"name": "sla_include_tf", "type": "int_value"},
        ],
    )
}}
