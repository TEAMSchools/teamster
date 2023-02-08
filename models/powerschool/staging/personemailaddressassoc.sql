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
        unique_key="personemailaddressassocid",
        transform_cols=[
            {"name": "personemailaddressassocid", "type": "int_value"},
            {"name": "personid", "type": "int_value"},
            {"name": "emailaddressid", "type": "int_value"},
            {"name": "emailtypecodesetid", "type": "int_value"},
            {"name": "isprimaryemailaddress", "type": "int_value"},
            {"name": "emailaddresspriorityorder", "type": "int_value"},
        ],
    )
}}
