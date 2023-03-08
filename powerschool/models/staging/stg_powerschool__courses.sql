{{
    teamster_utils.incremental_merge_source_file(
        file_uri=teamster_utils.get_gcs_uri(partition_path=var("partition_path")),
        unique_key="dcid",
        transform_cols=[
            {"name": "dcid", "transformation": "extract", "type": "int_value"},
            {"name": "id", "transformation": "extract", "type": "int_value"},
            {
                "name": "credit_hours",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "add_to_gpa",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "schoolid", "transformation": "extract", "type": "int_value"},
            {
                "name": "regavailable",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "targetclasssize",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "maxclasssize",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sectionstooffer",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "schoolgroup", "transformation": "extract", "type": "int_value"},
            {"name": "vocational", "transformation": "extract", "type": "int_value"},
            {"name": "status", "transformation": "extract", "type": "int_value"},
            {
                "name": "crhrweight",
                "transformation": "extract",
                "type": "double_value",
            },
            {"name": "sched_year", "transformation": "extract", "type": "int_value"},
            {
                "name": "sched_coursepackage",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_scheduled",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_sectionsoffered",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_teachercount",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_periodspermeeting",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_frequency",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_maximumperiodsperday",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_minimumperiodsperday",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_maximumdayspercycle",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_minimumdayspercycle",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_consecutiveperiods",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_blockstart",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_lengthinnumberofterms",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_consecutiveterms",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_balanceterms",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_maximumenrollment",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_concurrentflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_multiplerooms",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_labflag",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_labfrequency",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_labperiodspermeeting",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_repeatsallowed",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_loadpriority",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_substitutionallowed",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_usepreestablishedteams",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_closesectionaftermax",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_usesectiontypes",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_periodspercycle",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gradescaleid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "gpa_addedvalue",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "excludefromgpa",
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
                "name": "sched_lunchcourse",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "sched_do_not_print",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "exclude_ada", "transformation": "extract", "type": "int_value"},
            {"name": "programid", "transformation": "extract", "type": "int_value"},
            {
                "name": "excludefromstoredgrades",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "maxcredit",
                "transformation": "extract",
                "type": "double_value",
            },
            {
                "name": "iscareertech",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "whomodifiedid",
                "transformation": "extract",
                "type": "int_value",
            },
            {
                "name": "isfitnesscourse",
                "transformation": "extract",
                "type": "int_value",
            },
            {"name": "ispewaiver", "transformation": "extract", "type": "int_value"},
        ],
    )
}}
