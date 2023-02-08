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
        unique_key="studentcontactassocid",
        transform_cols=[
            {"name": "studentcontactassocid", "type": "int_value"},
            {"name": "studentdcid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "contactpriorityorder", "type": "int_value"},
            {"name": "currreltypecodesetid", "type": "int_value"},
        ],
    )
}}
