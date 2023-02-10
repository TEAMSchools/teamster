{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="assignmentcategoryassocid",
        transform_cols=[
            {"name": "assignmentcategoryassocid", "type": "int_value"},
            {"name": "assignmentsectionid", "type": "int_value"},
            {"name": "teachercategoryid", "type": "int_value"},
            {"name": "yearid", "type": "int_value"},
            {"name": "isprimary", "type": "int_value"},
            {"name": "whomodifiedid", "type": "int_value"},
        ],
    )
}}
