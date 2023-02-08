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
            {"name": "gradecalcformulaweightid", "type": "int_value"},
            {"name": "gradecalculationtypeid", "type": "int_value"},
            {"name": "teachercategoryid", "type": "int_value"},
            {"name": "districtteachercategoryid", "type": "int_value"},
            {"name": "assignmentid", "type": "int_value"},
            {"name": "weight", "type": "int_value"},
        ],
    )
}}
