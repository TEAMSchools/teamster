{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="assignmentsectionid",
        transform_cols=[
            {
                "name": "assignmentsectionid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {
                "name": "sectionsdcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "assignmentid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "relatedgradescaleitemdcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "scoreentrypoints",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "extracreditpoints",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "weight",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "totalpointvalue",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "iscountedinfinalgrade",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isscoringneeded",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "publishdaysbeforedue",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "publishedscoretypeid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isscorespublish",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "maxretakeallowed",
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
