{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "type": "int_value"},
            {"name": "id", "type": "int_value"},
            {"name": "sectionid", "type": "int_value"},
            {"name": "studentid", "type": "int_value"},
            {"name": "percent", "type": "double_value"},
            {"name": "points", "type": "double_value"},
            {"name": "pointspossible", "type": "double_value"},
            {"name": "varcredit", "type": "double_value"},
            {"name": "gradebooktype", "type": "int_value"},
            {"name": "calculatedpercent", "type": "double_value"},
            {"name": "isincomplete", "type": "int_value"},
            {"name": "isexempt", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
