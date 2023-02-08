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
        unique_key="usersdcid",
        transform_cols=[
            {"name": "usersdcid", "type": "int_value"},
            {"name": "smart_salary", "type": "int_value"},
            {"name": "smart_yearsinlea", "type": "int_value"},
            {"name": "smart_yearsinnj", "type": "int_value"},
            {"name": "smart_yearsofexp", "type": "int_value"},
            {"name": "excl_frm_smart_stf_submissn", "type": "int_value"},
            {"name": "smart_stafcompenanualsup", "type": "int_value"},
            {"name": "smart_stafcompnsatnbassal", "type": "int_value"},
        ],
    )
}}
