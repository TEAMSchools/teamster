{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradesectionconfigid",
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
