{{
    teamster_utils.generate_staging_model(
        unique_key="dcid.int_value",
        transform_cols=[
            {"name": "dcid", "extract": "int_value"},
            {"name": "id", "extract": "int_value"},
            {"name": "credit_hours", "extract": "double_value"},
            {"name": "add_to_gpa", "extract": "double_value"},
            {"name": "schoolid", "extract": "int_value"},
            {"name": "regavailable", "extract": "int_value"},
            {"name": "targetclasssize", "extract": "int_value"},
            {"name": "maxclasssize", "extract": "int_value"},
            {"name": "sectionstooffer", "extract": "int_value"},
            {"name": "schoolgroup", "extract": "int_value"},
            {"name": "vocational", "extract": "int_value"},
            {"name": "status", "extract": "int_value"},
            {"name": "crhrweight", "extract": "double_value"},
            {"name": "sched_year", "extract": "int_value"},
            {"name": "sched_coursepackage", "extract": "int_value"},
            {"name": "sched_scheduled", "extract": "int_value"},
            {"name": "sched_sectionsoffered", "extract": "int_value"},
            {"name": "sched_teachercount", "extract": "int_value"},
            {"name": "sched_periodspermeeting", "extract": "int_value"},
            {"name": "sched_frequency", "extract": "int_value"},
            {"name": "sched_maximumperiodsperday", "extract": "int_value"},
            {"name": "sched_minimumperiodsperday", "extract": "int_value"},
            {"name": "sched_maximumdayspercycle", "extract": "int_value"},
            {"name": "sched_minimumdayspercycle", "extract": "int_value"},
            {"name": "sched_consecutiveperiods", "extract": "int_value"},
            {"name": "sched_blockstart", "extract": "int_value"},
            {"name": "sched_lengthinnumberofterms", "extract": "int_value"},
            {"name": "sched_consecutiveterms", "extract": "int_value"},
            {"name": "sched_balanceterms", "extract": "int_value"},
            {"name": "sched_maximumenrollment", "extract": "int_value"},
            {"name": "sched_concurrentflag", "extract": "int_value"},
            {"name": "sched_multiplerooms", "extract": "int_value"},
            {"name": "sched_labflag", "extract": "int_value"},
            {"name": "sched_labfrequency", "extract": "int_value"},
            {"name": "sched_labperiodspermeeting", "extract": "int_value"},
            {"name": "sched_repeatsallowed", "extract": "int_value"},
            {"name": "sched_loadpriority", "extract": "int_value"},
            {"name": "sched_substitutionallowed", "extract": "int_value"},
            {"name": "sched_usepreestablishedteams", "extract": "int_value"},
            {"name": "sched_closesectionaftermax", "extract": "int_value"},
            {"name": "sched_usesectiontypes", "extract": "int_value"},
            {"name": "sched_periodspercycle", "extract": "int_value"},
            {"name": "gradescaleid", "extract": "int_value"},
            {"name": "gpa_addedvalue", "extract": "double_value"},
            {"name": "excludefromgpa", "extract": "int_value"},
            {"name": "excludefromclassrank", "extract": "int_value"},
            {"name": "excludefromhonorroll", "extract": "int_value"},
            {"name": "sched_lunchcourse", "extract": "int_value"},
            {"name": "sched_do_not_print", "extract": "int_value"},
            {"name": "exclude_ada", "extract": "int_value"},
            {"name": "programid", "extract": "int_value"},
            {"name": "excludefromstoredgrades", "extract": "int_value"},
            {"name": "maxcredit", "extract": "double_value"},
            {"name": "iscareertech", "extract": "int_value"},
            {"name": "whomodifiedid", "extract": "int_value"},
            {"name": "isfitnesscourse", "extract": "int_value"},
            {"name": "ispewaiver", "extract": "int_value"},
        ],
        except_cols=[
            "_dagster_partition_fiscal_year",
            "_dagster_partition_date",
            "_dagster_partition_hour",
            "_dagster_partition_minute",
        ],
    )
}}

select *
from staging
