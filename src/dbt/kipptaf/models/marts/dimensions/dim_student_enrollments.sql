with
    homeroom_sections as (
        select
            cc.cc_studentid,
            cc.cc_yearid,
            cc.sections_schoolid,
            cc._dbt_source_project,
            cc.cc_dateenrolled,
            cc.cc_dateleft,

            {{
                dbt_utils.generate_surrogate_key(
                    ["cc.sections_dcid", "cc._dbt_source_project"]
                )
            }} as course_section_key,
        from {{ ref("base_powerschool__course_enrollments") }} as cc
        where
            -- HR/Advisory credit-type test is duplicated in
            -- dim_student_section_enrollments.sql (is_homeroom column), which
            -- flags homeroom sections independently to avoid a build cycle.
            -- Keep the credit-type list in sync across both.
            cc.courses_credittype in ('HR', 'Advisory')
            and not cc.is_dropped_section
            and not cc.is_dropped_course
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    homeroom_teacher as (
        select
            hs.cc_dateenrolled,

            bcst.effective_start_date,
            bcst.staff_key as homeroom_teacher_staff_key,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "s.student_number",
                        "s._dbt_source_project",
                        "s.academic_year",
                        "s.entrydate",
                    ]
                )
            }} as student_enrollment_key,
        from homeroom_sections as hs
        inner join
            {{ ref("int_powerschool__student_enrollment_union") }} as s
            on hs.cc_studentid = s.studentid
            and hs.sections_schoolid = s.schoolid
            and hs.cc_yearid = s.yearid
            and hs._dbt_source_project = s._dbt_source_project
            and hs.cc_dateenrolled >= s.entrydate
            and hs.cc_dateenrolled < s.exitdate
        left join
            {{ ref("bridge_course_section_teachers") }} as bcst
            on hs.course_section_key = bcst.course_section_key
            and bcst.`role` = 'Lead Teacher'
            and bcst.effective_start_date
            < coalesce(hs.cc_dateleft, cast('9999-12-31' as date))
            and hs.cc_dateenrolled
            < coalesce(bcst.effective_end_date, cast('9999-12-31' as date))
    ),

    homeroom_resolved as (
        {{
            dbt_utils.deduplicate(
                relation="homeroom_teacher",
                partition_by="student_enrollment_key",
                order_by="cc_dateenrolled desc, effective_start_date desc",
            )
        }}
    ),

    enrollments as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "enr.student_number",
                        "enr._dbt_source_project",
                        "enr.academic_year",
                        "enr.entrydate",
                    ]
                )
            }} as student_enrollment_key,

            {{ dbt_utils.generate_surrogate_key(["enr.student_number"]) }}
            as student_key,

            sch.location_key,

            enr.entrydate as entry_date_key,
            enr.exitdate as exit_date_key,

            enr.academic_year,
            enr.grade_level,
            enr.cohort_primary as graduation_year,
            enr.is_retained_year,
            enr.year_in_network,
        from {{ ref("int_powerschool__student_enrollment_union") }} as enr
        left join
            {{ ref("stg_powerschool__schools") }} as sch
            on enr.schoolid = sch.school_number
            and enr._dbt_source_project = sch._dbt_source_project
    )

select
    e.student_enrollment_key,
    e.student_key,
    e.location_key,
    e.entry_date_key,
    e.exit_date_key,
    e.academic_year,
    e.grade_level,
    e.graduation_year,
    e.is_retained_year,
    e.year_in_network,

    hr.homeroom_teacher_staff_key,
from enrollments as e
left join
    homeroom_resolved as hr on e.student_enrollment_key = hr.student_enrollment_key
