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
            {"name": "gradesectionconfigid", "type": "int_value"},
            {"name": "sectionsdcid", "type": "int_value"},
            {"name": "gradeformulasetid", "type": "int_value"},
            {"name": "defaultdecimalcount", "type": "int_value"},
            {"name": "iscalcformulaeditable", "type": "int_value"},
            {"name": "isdropscoreeditable", "type": "int_value"},
            {"name": "iscalcprecisioneditable", "type": "int_value"},
            {"name": "isstndcalcmeteditable", "type": "int_value"},
            {"name": "isstndrcntscoreeditable", "type": "int_value"},
            {"name": "ishigherlvlstndeditable", "type": "int_value"},
            {"name": "ishigherstndautocalc", "type": "int_value"},
            {"name": "ishigherstndcalceditable", "type": "int_value"},
            {"name": "iscalcsectionfromstndedit", "type": "int_value"},
            {"name": "issectstndweighteditable", "type": "int_value"},
            {"name": "minimumassignmentvalue", "type": "int_value"},
            {"name": "isgradescaleteachereditable", "type": "int_value"},
            {"name": "isusingpercentforstndautocalc", "type": "int_value"},
        ],
    )
}}
