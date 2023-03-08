{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "studentid", "transformation": "extract", "type": "int_value"},
            {"name": "sectionid", "transformation": "extract", "type": "int_value"},
            {"name": "termid", "transformation": "extract", "type": "int_value"},
            {"name": "percent", "transformation": "extract", "type": "double_value"},
            {"name": "absences", "transformation": "extract", "type": "double_value"},
            {"name": "tardies", "transformation": "extract", "type": "double_value"},
            {
                "name": "potentialcrhrs",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "earnedcrhrs",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "grade_level", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {
                "name": "excludefromgpa",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gpa_points",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "gpa_addedvalue",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "gpa_custom2",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "excludefromclassrank",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excludefromhonorroll",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isearnedcrhrsfromgb",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "ispotentialcrhrsfromgb",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excludefromtranscripts",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "replaced_dcid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excludefromgraduation",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excludefromgradesuppression",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradereplacementpolicy_id",
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
