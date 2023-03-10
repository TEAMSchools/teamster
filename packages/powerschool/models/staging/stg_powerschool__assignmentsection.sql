{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="assignmentsectionid",
        transform_cols=[
            {
                "name": "assignmentsectionid",
                "extract": "int_value",
            },
            {"name": "yearid", "extract": "int_value"},
            {
                "name": "sectionsdcid",
                "extract": "int_value",
            },
            {
                "name": "assignmentid",
                "extract": "int_value",
            },
            {
                "name": "relatedgradescaleitemdcid",
                "extract": "int_value",
            },
            {
                "name": "scoreentrypoints",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "extracreditpoints",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "weight",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "totalpointvalue",
                "extract": "bytes_decimal_value",
            },
            {
                "name": "iscountedinfinalgrade",
                "extract": "int_value",
            },
            {
                "name": "isscoringneeded",
                "extract": "int_value",
            },
            {
                "name": "publishdaysbeforedue",
                "extract": "int_value",
            },
            {
                "name": "publishedscoretypeid",
                "extract": "int_value",
            },
            {
                "name": "isscorespublish",
                "extract": "int_value",
            },
            {
                "name": "maxretakeallowed",
                "extract": "int_value",
            },
            {
                "name": "whomodifiedid",
                "extract": "int_value",
            },
        ],
    )
}}
