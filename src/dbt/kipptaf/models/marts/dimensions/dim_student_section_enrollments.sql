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
            cc.cc_course_number,
            cc.teachernumber,

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
            er.cc_course_number,
            er.teachernumber,
            er.enr_source_project,
            er.enr_student_number,
            er.enr_academic_year,
            er.enr_entrydate,

            rt.`type` as rt_type,
            rt.code as rt_code,
            rt.`name` as rt_name,
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
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    section_enrollments as (
        select
            cc_academic_year as academic_year,
            cc_dateenrolled as entry_date,
            cc_dateleft as exit_date,
            is_dropped_section,
            is_dropped_course,
            cc_course_number,
            teachernumber,
            enr_source_project,
            enr_student_number,

            {{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
            as student_section_enrollment_key,

            {{
                dbt_utils.generate_surrogate_key(
                    ["sections_dcid", "_dbt_source_project"]
                )
            }} as course_section_key,

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
    ),

    -- Reporting terms are not unique on (powerschool_term_id, school, region) —
    -- one term id maps to several reporting quarters — so the term join fans a
    -- section enrollment across quarters. Collapse to one row per PK (the model
    -- grain); term_key resolves to a single deterministic quarter, as before.
    section_enrollments_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="section_enrollments",
                partition_by="student_section_enrollment_key",
                order_by="term_key asc",
            )
        }}
    ),

    section_enrollments_resolved as (
        select
            se.academic_year,
            se.entry_date,
            se.exit_date,
            se.is_dropped_section,
            se.is_dropped_course,
            se.cc_course_number,
            se.student_section_enrollment_key,
            se.course_section_key,
            se.student_enrollment_key,
            se.term_key,

            if(
                sr.employee_number is not null,
                {{ dbt_utils.generate_surrogate_key(["sr.employee_number"]) }},
                cast(null as string)
            ) as lead_teacher_staff_key,

            row_number() over (
                partition by
                    se.enr_student_number,
                    se.enr_source_project,
                    se.academic_year,
                    se.cc_course_number
                order by
                    (se.is_dropped_section or se.is_dropped_course) asc,
                    coalesce(se.exit_date, cast('9999-12-31' as date)) desc,
                    se.entry_date desc,
                    se.student_section_enrollment_key asc
            ) as course_enrollment_rank,
        from section_enrollments_deduped as se
        left join
            {{ ref("int_people__staff_roster") }} as sr
            on se.teachernumber = sr.powerschool_teacher_number
    )

select
    academic_year,
    entry_date,
    exit_date,
    is_dropped_section,
    is_dropped_course,
    student_section_enrollment_key,
    course_section_key,
    student_enrollment_key,
    term_key,
    lead_teacher_staff_key,

    coalesce(cc_course_number like 'HR%', false) as is_homeroom,
    (course_enrollment_rank = 1) as is_current_section_enrollment,
from section_enrollments_resolved
