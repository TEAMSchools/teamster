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
            {"name": "assignmentscoreid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "assignmentsectionid", "type": "int_value"},
            {"name": "studentsdcid", "type": "int_value"},
            {"name": "islate", "type": "int_value"},
            {"name": "iscollected", "type": "int_value"},
            {"name": "isexempt", "type": "int_value"},
            {"name": "ismissing", "type": "int_value"},
            {"name": "isabsent", "type": "int_value"},
            {"name": "isincomplete", "type": "int_value"},
            {"name": "actualscoregradescaledcid", "type": "int_value"},
            {"name": "scorepercent", "type": "int_value"},
            {"name": "scorepoints", "type": "int_value"},
            {"name": "scorenumericgrade", "type": "int_value"},
            {"name": "scoregradescaledcid", "type": "int_value"},
            {"name": "altnumericgrade", "type": "int_value"},
            {"name": "altscoregradescaledcid", "type": "int_value"},
            {"name": "hasretake", "type": "int_value"},
            {"name": "authoredbyuc", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
