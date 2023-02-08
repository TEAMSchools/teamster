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
            {"name": "prefixcodesetid", "type": "int_value"},
            {"name": "suffixcodesetid", "type": "int_value"},
            {"name": "gendercodesetid", "type": "int_value"},
            {"name": "statecontactnumber", "type": "int_value"},
            {"name": "isactive", "type": "int_value"},
            {"name": "excludefromstatereporting", "type": "int_value"},
        ],
    )
}}
