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
        unique_key="",
        transform_cols=[
            {"name": "gradeformulasetid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "iscoursegradecalculated", "type": "int_value"},
            {"name": "isreporttermsetupsame", "type": "int_value"},
            {"name": "sectionsdcid", "type": "int_value"},
        ],
    )
}}
