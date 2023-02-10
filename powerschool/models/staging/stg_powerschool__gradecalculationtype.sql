{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
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
