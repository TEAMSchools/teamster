{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradeformulasetid",
        transform_cols=[
            {
                "name": "gradeformulasetid",
                "extract": "int_value",
            },
            {"name": "yearid", "extract": "int_value"},
            {
                "name": "iscoursegradecalculated",
                "extract": "int_value",
            },
            {
                "name": "isreporttermsetupsame",
                "extract": "int_value",
            },
            {
                "name": "sectionsdcid",
                "extract": "int_value",
            },
        ],
    )
}}
