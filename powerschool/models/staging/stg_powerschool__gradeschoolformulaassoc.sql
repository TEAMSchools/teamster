{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="gradeschoolformulaassocid",
        transform_cols=[
            {
                "name": "gradeschoolformulaassocid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradeformulasetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradeschoolconfigid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isdefaultformulaset",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
