{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "sectionid", "transformation": "extract", "type": "int_value"},
            {"name": "studentid", "transformation": "extract", "type": "int_value"},
            {"name": "percent", "transformation": "extract", "type": "double_value"},
            {"name": "points", "transformation": "extract", "type": "double_value"},
            {
                "name": "pointspossible",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "varcredit",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "gradebooktype",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "calculatedpercent",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "isincomplete",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isexempt", "transformation": "extract", "type": "int_value"},
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
