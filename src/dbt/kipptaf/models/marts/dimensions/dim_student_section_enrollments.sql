with
    student_enrollments as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            yearid,
            student_number,
            entrydate,
            exitdate,
        from {{ ref("base_powerschool__student_enrollments") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["cc.cc_dcid", "cc._dbt_source_relation"]) }}
    as student_section_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "cc.cc_academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["cc.sections_dcid", "cc._dbt_source_relation"]
        )
    }} as course_section_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,

    cc.students_student_number as student_number,
    cc.cc_academic_year as academic_year,
    cc.cc_dateenrolled as date_enrolled,
    cc.cc_dateleft as date_left,
    cc.is_dropped_section,
    cc.is_dropped_course,

from {{ ref("base_powerschool__course_enrollments") }} as cc
left join
    student_enrollments as enr
    on cc.cc_studentid = enr.studentid
    and cc.sections_schoolid = enr.schoolid
    and cc.cc_yearid = enr.yearid
    and cc.cc_dateenrolled >= enr.entrydate
    and cc.cc_dateenrolled < enr.exitdate
    and {{ union_dataset_join_clause(left_alias="cc", right_alias="enr") }}
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cc.cc_abs_termid = rt.powerschool_term_id
    and cc.sections_schoolid = rt.school_id
    and cc.region = rt.region
