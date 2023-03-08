{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "student_number",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "enroll_status",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "grade_level", "transformation": "extract", "type": "int_value"},
            {"name": "balance1", "transformation": "extract", "type": "double_value"},
            {"name": "balance2", "transformation": "extract", "type": "double_value"},
            {"name": "phone_id", "transformation": "extract", "type": "int_value"},
            {"name": "lunch_id", "transformation": "extract", "type": "double_value"},
            {"name": "photoflag", "transformation": "extract", "type": "int_value"},
            {"name": "sdatarn", "transformation": "extract", "type": "int_value"},
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {
                "name": "allowwebaccess",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "cumulative_gpa",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "simple_gpa",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "cumulative_pct",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "simple_pct",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "classof", "transformation": "extract", "type": "int_value"},
            {"name": "next_school", "transformation": "extract", "type": "int_value"},
            {
                "name": "exclude_fr_rank",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "teachergroupid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "campusid", "transformation": "extract", "type": "int_value"},
            {"name": "balance3", "transformation": "extract", "type": "double_value"},
            {"name": "balance4", "transformation": "extract", "type": "double_value"},
            {
                "name": "enrollment_schoolid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradreqsetid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "student_allowwebaccess",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "wm_tier", "transformation": "extract", "type": "int_value"},
            {
                "name": "wm_createtime",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_yearofgraduation",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_nextyeargrade",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_scheduled",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_lockstudentschedule",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_priority",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "districtentrygradelevel",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "schoolentrygradelevel",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "graduated_schoolid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "graduated_rank",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "customrank_gpa",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "state_excludefromreporting",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "state_enrollflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "enrollmentcode",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fulltimeequiv_obsolete",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "membershipshare",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "tuitionpayer",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fee_exemption_status",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "fteid", "transformation": "extract", "type": "int_value"},
            {
                "name": "sched_loadlock",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "person_id", "transformation": "extract", "type": "int_value"},
            {"name": "ldapenabled", "transformation": "extract", "type": "int_value"},
            {
                "name": "summerschoolid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fedethnicity",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "fedracedecline",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "gpentryyear", "transformation": "extract", "type": "int_value"},
            {
                "name": "enrollmentid",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "ismigrated", "transformation": "extract", "type": "int_value"},
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
        ],
    )
}}
