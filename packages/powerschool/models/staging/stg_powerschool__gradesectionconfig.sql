{{
    teamster_utils.transform_cols_base_model(
        transform_cols=[
            {"name": "gradesectionconfigid", "extract": "int_value"},
            {"name": "sectionsdcid", "extract": "int_value"},
            {"name": "gradeformulasetid", "extract": "int_value"},
            {"name": "defaultdecimalcount", "extract": "int_value"},
            {"name": "iscalcformulaeditable", "extract": "int_value"},
            {"name": "isdropscoreeditable", "extract": "int_value"},
            {"name": "iscalcprecisioneditable", "extract": "int_value"},
            {"name": "isstndcalcmeteditable", "extract": "int_value"},
            {"name": "isstndrcntscoreeditable", "extract": "int_value"},
            {"name": "ishigherlvlstndeditable", "extract": "int_value"},
            {"name": "ishigherstndautocalc", "extract": "int_value"},
            {"name": "ishigherstndcalceditable", "extract": "int_value"},
            {"name": "iscalcsectionfromstndedit", "extract": "int_value"},
            {"name": "issectstndweighteditable", "extract": "int_value"},
            {"name": "minimumassignmentvalue", "extract": "int_value"},
            {"name": "isgradescaleteachereditable", "extract": "int_value"},
            {"name": "isusingpercentforstndautocalc", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

{# {{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradesectionconfigid",
        transform_cols=[
            {"name": "gradesectionconfigid", "extract": "int_value"},
            {"name": "sectionsdcid", "extract": "int_value"},
            {"name": "gradeformulasetid", "extract": "int_value"},
            {"name": "defaultdecimalcount", "extract": "int_value"},
            {"name": "iscalcformulaeditable", "extract": "int_value"},
            {"name": "isdropscoreeditable", "extract": "int_value"},
            {"name": "iscalcprecisioneditable", "extract": "int_value"},
            {"name": "isstndcalcmeteditable", "extract": "int_value"},
            {"name": "isstndrcntscoreeditable", "extract": "int_value"},
            {"name": "ishigherlvlstndeditable", "extract": "int_value"},
            {"name": "ishigherstndautocalc", "extract": "int_value"},
            {"name": "ishigherstndcalceditable", "extract": "int_value"},
            {"name": "iscalcsectionfromstndedit", "extract": "int_value"},
            {"name": "issectstndweighteditable", "extract": "int_value"},
            {"name": "minimumassignmentvalue", "extract": "int_value"},
            {"name": "isgradescaleteachereditable", "extract": "int_value"},
            {"name": "isusingpercentforstndautocalc", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}} #}

