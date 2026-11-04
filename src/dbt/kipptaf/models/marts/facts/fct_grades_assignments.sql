with
    course_enrollments as (
        select
            _dbt_source_project,
            cc_academic_year,
            cc_schoolid,
            cc_dcid,
            cc_dateenrolled,
            cc_dateleft,
            sections_dcid,
            students_student_number,
            region,
        from {{ ref("int_students__course_enrollments") }}
        where not is_dropped_section
    ),

    student_enrollments as (
        select
            _dbt_source_project,
            schoolid,
            academic_year,
            student_number,
            entrydate,
            exitdate,
        from {{ ref("int_students__student_enrollment_union") }}
    ),

    reporting_terms as (
        select
            `type`,
            code,
            `name`,
            `start_date`,
            end_date,
            region,
            school_id,
            grade_band,
            powerschool_year_id,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "asg.assignmentsectionid",
                "asg._dbt_source_project",
                "asg.students_dcid",
            ]
        )
    }} as grades_assignment_key,

    {{ dbt_utils.generate_surrogate_key(["ce.cc_dcid", "ce._dbt_source_project"]) }}
    as student_section_enrollment_key,

    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                    "rt.grade_band",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    asg.duedate as due_date_key,

    asg.academic_year,

    asg.assignment_name as `name`,
    asg.category_name,
    asg.category_code,

    asg.points_earned,
    asg.numeric_grade_earned,
    asg.totalpointvalue as max_points,
    asg.assign_final_score_percent as score_percent,

    if(asg.is_missing is null, null, asg.is_missing = 1) as is_missing,
    if(asg.is_late = 1, true, false) as is_late,
    if(asg.is_exempt = 1, true, false) as is_exempt,
    asg.is_expected,
    if(asg.iscountedinfinalgrade = 1, true, false) as is_counted_in_final_grade,
from {{ ref("int_students__gradebook_assignments_scores") }} as asg
inner join
    course_enrollments as ce
    on asg.sectionsdcid = ce.sections_dcid
    -- student_number, not students_dcid: students_dcid is null on every Miami
    -- row of int_students__course_enrollments. The swap is 1:1 inside every NJ
    -- district -- (sections_dcid, students_dcid) and (sections_dcid,
    -- students_student_number) yield identical distinct counts -- so no NJ row
    -- moves. The surrogate key still reads asg.students_dcid.
    and asg.student_number = ce.students_student_number
    and asg.duedate >= ce.cc_dateenrolled
    -- cc_dateleft is null on 18,582 of 19,398 Miami AY2026 course enrollments
    -- and on 0 NJ rows: `duedate < null` is null, which would drop nearly every
    -- Miami row. Miami-only in effect.
    and asg.duedate < coalesce(ce.cc_dateleft, date '9999-12-31')
    and asg._dbt_source_project = ce._dbt_source_project
-- retained as a row-population filter (assignment must fall within a covering
-- school enrollment); enrollment linkage now flows via
-- student_section_enrollment_key -> dim_student_section_enrollments
inner join
    student_enrollments as enr
    on ce.students_student_number = enr.student_number
    and ce.cc_schoolid = enr.schoolid
    -- academic_year on both sides. PowerSchool's yearid = academic_year - 1990
    -- has no Focus equivalent, and the swap is 1:1 for all 3 NJ regions.
    and ce.cc_academic_year = enr.academic_year
    and asg.duedate >= enr.entrydate
    and asg.duedate < enr.exitdate
    and ce._dbt_source_project = enr._dbt_source_project
left join
    reporting_terms as rt
    on asg.duedate between rt.start_date and rt.end_date
    and ce.cc_schoolid = rt.school_id
    and ce.region = rt.region
