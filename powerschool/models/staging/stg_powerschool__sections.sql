{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {"name": "teacher", "transformation": "extract", "type": "int_value"},
            {"name": "termid", "transformation": "extract", "type": "int_value"},
            {
                "name": "no_of_students",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {"name": "noofterms", "transformation": "extract", "type": "int_value"},
            {
                "name": "trackteacheratt",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "maxenrollment",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "distuniqueid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "wheretaught", "transformation": "extract", "type": "int_value"},
            {
                "name": "rostermodser",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "pgversion", "transformation": "extract", "type": "int_value"},
            {"name": "grade_level", "transformation": "extract", "type": "int_value"},
            {"name": "campusid", "transformation": "extract", "type": "int_value"},
            {"name": "exclude_ada", "transformation": "extract", "type": "int_value"},
            {
                "name": "gradescaleid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "excludefromgpa",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "buildid", "transformation": "extract", "type": "int_value"},
            {
                "name": "schedulesectionid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "wheretaughtdistrict",
                "transformation": "extract",
                "type": "int_value",
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
                "name": "parent_section_id",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "attendance_type_code",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "maxcut", "transformation": "extract", "type": "int_value"},
            {
                "name": "exclude_state_rpt_yn",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "sortorder", "transformation": "extract", "type": "int_value"},
            {"name": "programid", "transformation": "extract", "type": "int_value"},
            {
                "name": "excludefromstoredgrades",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradebooktype",
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
