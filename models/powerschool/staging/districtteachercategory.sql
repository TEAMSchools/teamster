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
        unique_key="districtteachercategoryid",
        transform_cols=[
            {"name": "districtteachercategoryid", "type": "int_value"},
            {"name": "isinfinalgrades", "type": "int_value"},
            {"name": "isactive", "type": "int_value"},
            {"name": "isusermodifiable", "type": "int_value"},
            {"name": "displayposition", "type": "int_value"},
            {"name": "defaultscoreentrypoints", "type": "int_value"},
            {"name": "defaultextracreditpoints", "type": "int_value"},
            {"name": "defaultweight", "type": "int_value"},
            {"name": "defaulttotalvalue", "type": "int_value"},
            {"name": "isdefaultpublishscores", "type": "int_value"},
            {"name": "defaultdaysbeforedue", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
