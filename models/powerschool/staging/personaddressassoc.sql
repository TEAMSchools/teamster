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
        unique_key="personaddressassocid",
        transform_cols=[
            {"name": "personaddressassocid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "personaddressid", "type": "int_value"},
            {"name": "addresstypecodesetid", "type": "int_value"},
            {"name": "addresspriorityorder", "type": "int_value"},
        ],
    )
}}
