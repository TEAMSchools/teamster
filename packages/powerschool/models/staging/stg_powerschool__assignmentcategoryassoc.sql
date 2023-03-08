{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="assignmentcategoryassocid",
        transform_cols=[
            {
                "name": "assignmentcategoryassocid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "assignmentsectionid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "teachercategoryid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "yearid",
                "transformation": "extract",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isprimary",
                "transformation": "extract",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
