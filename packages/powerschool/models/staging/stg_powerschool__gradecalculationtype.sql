{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradecalculationtypeid",
        transform_cols=[
            {
                "name": "gradecalculationtypeid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradeformulasetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {"name": "isnograde", "transformation": "extract", "type": "int_value"},
            {
                "name": "isdroplowstudentfavor",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isalternatepointsused",
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
        ],
    )
}}
