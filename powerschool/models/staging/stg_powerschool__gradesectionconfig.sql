{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradesectionconfigid",
        transform_cols=[
            {
                "name": "gradesectionconfigid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sectionsdcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradeformulasetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "defaultdecimalcount",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscalcformulaeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isdropscoreeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscalcprecisioneditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isstndcalcmeteditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isstndrcntscoreeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ishigherlvlstndeditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ishigherstndautocalc",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ishigherstndcalceditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "iscalcsectionfromstndedit",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "issectstndweighteditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "minimumassignmentvalue",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isgradescaleteachereditable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isusingpercentforstndautocalc",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
