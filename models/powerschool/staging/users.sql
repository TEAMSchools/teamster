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
            {"name": "homeschoolid", "type": "int_value"},
            {"name": "photo", "type": "int_value"},
            {"name": "numlogins", "type": "int_value"},
            {"name": "allowloginstart", "type": "int_value"},
            {"name": "allowloginend", "type": "int_value"},
            {"name": "psaccess", "type": "int_value"},
            {"name": "groupvalue", "type": "int_value"},
            {"name": "lunch_id", "type": "double_value"},
            {"name": "supportcontact", "type": "int_value"},
            {"name": "wm_tier", "type": "int_value"},
            {"name": "wm_createtime", "type": "int_value"},
            {"name": "wm_exclude", "type": "int_value"},
            {"name": "adminldapenabled", "type": "int_value"},
            {"name": "teacherldapenabled", "type": "int_value"},
            {"name": "maximum_load", "type": "int_value"},
            {"name": "gradebooktype", "type": "int_value"},
            {"name": "fedethnicity", "type": "int_value"},
            {"name": "fedracedecline", "type": "int_value"},
            {"name": "ptaccess", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
