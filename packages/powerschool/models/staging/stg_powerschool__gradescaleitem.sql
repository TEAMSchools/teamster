{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "gradescaleid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isforcoursegrade",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isforstandards",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "isgpashown", "transformation": "extract", "type": "int_value"},
            {"name": "countsingpa", "transformation": "extract", "type": "int_value"},
            {
                "name": "displayposition",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "grade_points",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "addedvalue", "transformation": "extract", "type": "int_value"},
            {
                "name": "graduationcredit",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "teacherscale",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "cutoffpercentage",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "value", "transformation": "extract", "type": "int_value"},
            {"name": "colorlevels", "transformation": "extract", "type": "int_value"},
            {
                "name": "isproficient",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isscorecodeonassignments",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "modify_code", "transformation": "extract", "type": "int_value"},
            {"name": "numericmin", "transformation": "extract", "type": "int_value"},
            {"name": "numericmax", "transformation": "extract", "type": "int_value"},
            {
                "name": "numericdecimals",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "numericcutoff",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "numericvalue",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "hasspecialgrades",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "specialgradescaledcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "hasrelatedscales",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "altconvertgradescaledcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "altfinalnumericcutoff",
                "transformation": "extract",
                "type": "bytes_decimal_value",
            },
            {
                "name": "istermweightingshown",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "alt_grade_points",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "cutoffpoints",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excludefromafg",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "grade_replacement_policy",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "parentgradescaledcid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
