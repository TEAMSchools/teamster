with
    student_enrollments as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            studentid,
            schoolid,
            yearid,
            student_number,
            academic_year,
            entrydate,
            exitdate,
        from {{ ref("int_powerschool__student_enrollment_union") }}
    ),

    course_enrollments_joined as (
        select
            cc._dbt_source_relation,
            cc._dbt_source_project,
            cc.cc_dcid,
            cc.sections_dcid,
            cc.cc_academic_year,
            cc.cc_dateenrolled,
            cc.cc_dateleft,
            cc.is_dropped_section,
            cc.is_dropped_course,

            enr._dbt_source_project as enr_source_project,
            enr.student_number as enr_student_number,
            enr.academic_year as enr_academic_year,
            enr.entrydate as enr_entrydate,

            rt.`type` as rt_type,
            rt.code as rt_code,
            rt.name as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,
        from {{ ref("base_powerschool__course_enrollments") }} as cc
        left join
            student_enrollments as enr
            on cc.cc_studentid = enr.studentid
            and cc.sections_schoolid = enr.schoolid
            and cc.cc_yearid = enr.yearid
            and cc.cc_dateenrolled >= enr.entrydate
            and cc.cc_dateenrolled < enr.exitdate
            and cc._dbt_source_project = enr._dbt_source_project
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on cc.cc_abs_termid = rt.powerschool_term_id
            and cc.sections_schoolid = rt.school_id
            and cc.region = rt.region
            and rt.`type` = 'RT'
    )

select
    cc_academic_year as academic_year,
    cc_dateenrolled as entry_date,
    cc_dateleft as exit_date,
    is_dropped_section,
    is_dropped_course,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
    as student_section_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["sections_dcid", "_dbt_source_project"]) }}
    as course_section_key,

    if(
        enr_student_number is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "enr_student_number",
                    "enr_source_project",
                    "enr_academic_year",
                    "enr_entrydate",
                ]
            )
        }},
        cast(null as string)
    ) as student_enrollment_key,

    if(
        rt_code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt_type",
                    "rt_code",
                    "rt_name",
                    "rt_start_date",
                    "rt_region",
                    "rt_school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
from course_enrollments_joined
