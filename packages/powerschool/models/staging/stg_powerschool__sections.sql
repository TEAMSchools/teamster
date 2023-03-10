{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "teacher", "extract": "int_value"},
            {"name": "termid", "extract": "int_value"},
            {
                "name": "no_of_students",
                "extract": "int_value",
            },
            {"name": "schoolid", "extract": "int_value"},
            {"name": "noofterms", "extract": "int_value"},
            {
                "name": "trackteacheratt",
                "extract": "int_value",
            },
            {
                "name": "maxenrollment",
                "extract": "int_value",
            },
            {
                "name": "distuniqueid",
                "extract": "int_value",
            },
            {"name": "wheretaught", "extract": "int_value"},
            {
                "name": "rostermodser",
                "extract": "int_value",
            },
            {"name": "pgversion", "extract": "int_value"},
            {"name": "grade_level", "extract": "int_value"},
            {"name": "campusid", "extract": "int_value"},
            {"name": "exclude_ada", "extract": "int_value"},
            {
                "name": "gradescaleid",
                "extract": "int_value",
            },
            {
                "name": "excludefromgpa",
                "extract": "int_value",
            },
            {"name": "buildid", "extract": "int_value"},
            {
                "name": "schedulesectionid",
                "extract": "int_value",
            },
            {
                "name": "wheretaughtdistrict",
                "extract": "int_value",
            },
            {
                "name": "excludefromclassrank",
                "extract": "int_value",
            },
            {
                "name": "excludefromhonorroll",
                "extract": "int_value",
            },
            {
                "name": "parent_section_id",
                "extract": "int_value",
            },
            {
                "name": "attendance_type_code",
                "extract": "int_value",
            },
            {"name": "maxcut", "extract": "int_value"},
            {
                "name": "exclude_state_rpt_yn",
                "extract": "int_value",
            },
            {"name": "sortorder", "extract": "int_value"},
            {"name": "programid", "extract": "int_value"},
            {
                "name": "excludefromstoredgrades",
                "extract": "int_value",
            },
            {
                "name": "gradebooktype",
                "extract": "int_value",
            },
            {
                "name": "whomodifiedid",
                "extract": "int_value",
            },
        ],
    )
}}
