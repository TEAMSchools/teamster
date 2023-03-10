{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="assignmentcategoryassocid",
        transform_cols=[
            {
                "name": "assignmentcategoryassocid",
                "extract": "int_value",
            },
            {
                "name": "assignmentsectionid",
                "extract": "int_value",
            },
            {
                "name": "teachercategoryid",
                "extract": "int_value",
            },
            {
                "name": "yearid",
                "extract": "int_value",
            },
            {
                "name": "isprimary",
                "extract": "int_value",
            },
            {
                "name": "whomodifiedid",
                "extract": "int_value",
            },
        ],
    )
}}
