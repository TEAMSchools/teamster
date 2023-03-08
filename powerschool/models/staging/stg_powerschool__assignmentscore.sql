{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="assignmentscoreid",
        transform_cols=[
            {
                "name": "assignmentscoreid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {
                "name": "assignmentsectionid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "studentsdcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "islate", "transformation": "extract", "type": "int_value"},
            {"name": "iscollected", "transformation": "extract", "type": "int_value"},
            {"name": "isexempt", "transformation": "extract", "type": "int_value"},
            {"name": "ismissing", "transformation": "extract", "type": "int_value"},
            {"name": "isabsent", "transformation": "extract", "type": "int_value"},
            {
                "name": "isincomplete",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "actualscoregradescaledcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "scorepercent",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "scorepoints",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "scorenumericgrade",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "scoregradescaledcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "altnumericgrade",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "altscoregradescaledcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "hasretake", "transformation": "extract", "type": "int_value"},
            {
                "name": "authoredbyuc",
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
