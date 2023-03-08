{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradeformulasetid",
        transform_cols=[
            {
                "name": "gradeformulasetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {
                "name": "iscoursegradecalculated",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isreporttermsetupsame",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sectionsdcid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
