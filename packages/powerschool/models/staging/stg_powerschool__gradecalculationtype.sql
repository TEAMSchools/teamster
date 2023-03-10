{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradecalculationtypeid",
        transform_cols=[
            {
                "name": "gradecalculationtypeid",
                "extract": "int_value",
            },
            {
                "name": "gradeformulasetid",
                "extract": "int_value",
            },
            {"name": "yearid", "extract": "int_value"},
            {"name": "isnograde", "extract": "int_value"},
            {
                "name": "isdroplowstudentfavor",
                "extract": "int_value",
            },
            {
                "name": "isalternatepointsused",
                "extract": "int_value",
            },
            {
                "name": "iscalcformulaeditable",
                "extract": "int_value",
            },
            {
                "name": "isdropscoreeditable",
                "extract": "int_value",
            },
        ],
    )
}}
