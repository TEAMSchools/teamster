{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "termid", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {
                "name": "creditpct",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "collect", "transformation": "extract", "type": "int_value"},
            {"name": "yearid", "transformation": "extract", "type": "int_value"},
            {
                "name": "showonspreadsht",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "currentgrade",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "storegrades", "transformation": "extract", "type": "int_value"},
            {
                "name": "numattpoints",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "suppressltrgrd",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradescaleid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "suppresspercentscr",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "aregradeslocked",
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
