with
    student_enrollments as (
        select
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

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment_overlap as (
        select
            cc._dbt_source_project,
            cc.cc_dcid,
            cc.sections_dcid,
            cc.cc_academic_year,
            cc.cc_dateenrolled,
            cc.cc_dateleft,
            cc.cc_abs_termid,
            cc.sections_schoolid,
            cc.region,
            cc.is_dropped_section,
            cc.is_dropped_course,

            enr._dbt_source_project as enr_source_project,
            enr.student_number as enr_student_number,
            enr.academic_year as enr_academic_year,
            enr.entrydate as enr_entrydate,

            (
                cc.cc_dateenrolled >= enr.entrydate
                and cc.cc_dateenrolled < enr.exitdate
            ) as is_covering,
        from {{ ref("base_powerschool__course_enrollments") }} as cc
        -- alumni placeholder rows (enroll_status=3) have NULL entrydate/exitdate
        -- and match no stint here, producing a NULL student_enrollment_key
        left join
            student_enrollments as enr
            on cc.cc_studentid = enr.studentid
            and cc.sections_schoolid = enr.schoolid
            and cc.cc_yearid = enr.yearid
            and cc._dbt_source_project = enr._dbt_source_project
            and cc.cc_dateleft > enr.entrydate
            and cc.cc_dateenrolled < enr.exitdate
    ),

    enrollment_resolved as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment_overlap",
                partition_by="cc_dcid, _dbt_source_project",
                order_by="is_covering desc, enr_entrydate asc",
            )
        }}
    ),

    course_enrollments_joined as (
        select
            er.cc_dcid,
            er._dbt_source_project,
            er.sections_dcid,
            er.cc_academic_year,
            er.cc_dateenrolled,
            er.cc_dateleft,
            er.is_dropped_section,
            er.is_dropped_course,
            er.enr_source_project,
            er.enr_student_number,
            er.enr_academic_year,
            er.enr_entrydate,

            rt.`type` as rt_type,
            rt.code as rt_code,
            rt.name as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,
        from enrollment_resolved as er
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on er.cc_abs_termid = rt.powerschool_term_id
            and er.sections_schoolid = rt.school_id
            and er.region = rt.region
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
