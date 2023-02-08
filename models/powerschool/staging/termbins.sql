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
            {"name": "termid", "type": "int_value"},
            {"name": "schoolid", "type": "int_value"},
            {"name": "creditpct", "type": "int_value"},
            {"name": "collect", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "showonspreadsht", "type": "int_value"},
            {"name": "currentgrade", "type": "int_value"},
            {"name": "storegrades", "type": "int_value"},
            {"name": "numattpoints", "type": "int_value"},
            {"name": "suppressltrgrd", "type": "int_value"},
            {"name": "gradescaleid", "type": "int_value"},
            {"name": "suppresspercentscr", "type": "int_value"},
            {"name": "aregradeslocked", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
