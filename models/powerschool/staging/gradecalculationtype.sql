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
        unique_key="gradecalculationtypeid",
        transform_cols=[
            {"name": "gradecalculationtypeid", "type": "int_value"},
            {"name": "gradeformulasetid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "isnograde", "type": "int_value"},
            {"name": "isdroplowstudentfavor", "type": "int_value"},
            {"name": "isalternatepointsused", "type": "int_value"},
            {"name": "iscalcformulaeditable", "type": "int_value"},
            {"name": "isdropscoreeditable", "type": "int_value"},
        ],
    )
}}
