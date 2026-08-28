with
    -- coalesce guards an empty int_focus__schedule (an unbuilt --defer dev
    -- copy): min() over no rows is NULL, `academic_year >= NULL` is NULL, so
    -- `not (...)` is NULL and the filter would drop every Miami archive row
    -- instead of keeping it. Same guard as int_students__course_enrollments.
    focus_academic_year_boundary as (
        select coalesce(min(academic_year), 9999) as min_academic_year,
        from {{ ref("int_focus__schedule") }}
    ),

    powerschool_conformed as (
        select
            asg._dbt_source_project,
            asg.assignmentsectionid,
            asg.sectionsdcid,
            asg.students_dcid,
            asg.student_number,
            asg.academic_year,
            asg.duedate,
            asg.assignment_name,
            asg.category_name,
            asg.category_code,
            asg.points_earned,
            asg.numeric_grade_earned,
            asg.totalpointvalue,
            asg.assign_final_score_percent,
            asg.is_missing,
            asg.is_late,
            asg.is_exempt,
            asg.is_expected,
            asg.iscountedinfinalgrade,

            -- PowerSchool dates assignments rather than storing them by term,
            -- so there is no marking period on a score. Carried as null so the
            -- Focus branch can supply one for int_students__category_grades.
            cast(null as int64) as marking_period_id,

        from {{ ref("int_powerschool__gradebook_assignments_scores") }} as asg
        cross join focus_academic_year_boundary as fay
        where
            not (
                asg._dbt_source_project = 'kippmiami'
                and asg.academic_year >= fay.min_academic_year
            )
    ),

    focus_conformed as (
        select
            gg._dbt_source_project,

            -- PowerSchool's assignmentsectionid is one row per assignment per
            -- section. Focus's exact analog is the assignment-to-course-period
            -- join row, whose id carries that same grain. Keeping the column
            -- name means fct_grades_assignments' surrogate key expression is
            -- untouched, so no NJ hash moves.
            ajcp.id as assignmentsectionid,

            gg.course_period_id as sectionsdcid,

            -- Focus's internal student row id, the students_dcid analog. Feeds
            -- grades_assignment_key only. The enrollment join in the fact uses
            -- student_number, which both branches carry.
            gg.student_id as students_dcid,

            st.student_number,

            mp.syear as academic_year,
            gg.marking_period_id,

            -- Focus stores day boundaries in local time as UTC: a due date
            -- lands at 03:59:59Z, which is 23:59:59 the PREVIOUS day in
            -- America/New_York. A bare date() shifts every due date forward one
            -- day, misfiling scores across quarter boundaries and against the
            -- enrollment window. The focus package cannot do this cast — its
            -- local_timezone var is UTC.
            date(gg.due_date, '{{ var("local_timezone") }}') as duedate,

            gg.assignment_title as assignment_name,
            gg.assignment_type_title as category_name,

            -- Focus's category titles share PowerSchool's storecode_type
            -- domain. An unmapped title falls through to itself, so a new Focus
            -- category surfaces in the fact rather than vanishing from it.
            case
                gg.assignment_type_title
                when 'Formative'
                then 'F'
                when 'Homework'
                then 'H'
                when 'Work Habits'
                then 'W'
                when 'Summative'
                then 'S'
                else gg.assignment_type_title
            end as category_code,

            -- points = -1 is Focus's not-yet-graded / excused sentinel, not a
            -- score. Left numeric it computes a score percent of -10 and
            -- poisons every category average that contains it.
            if(gg.points >= 0, cast(gg.points as float64), null) as points_earned,

            cast(gg.assignment_points as float64) as totalpointvalue,

            if(
                gg.points >= 0,
                round(
                    safe_divide(
                        cast(gg.points as float64),
                        cast(gg.assignment_points as float64)
                    )
                    * 100,
                    2
                ),
                null
            ) as assign_final_score_percent,

            -- Focus scores are points-based; there is no PERCENT / GRADESCALE
            -- score type carrying a numeric grade distinct from the points.
            cast(null as float64) as numeric_grade_earned,

            -- Focus records no missing flag on a gradebook score.
            cast(null as int64) as is_missing,

            if(gg.late, 1, 0) as is_late,
            if(gg.exclude_from_average, 1, 0) as is_exempt,
            if(gg.assignment_exclude_from_average, 0, 1) as iscountedinfinalgrade,

            (
                not (gg.exclude_from_average or gg.assignment_exclude_from_average)
            ) as is_expected,

        from {{ ref("int_focus__gradebook_grades") }} as gg
        -- inner, not left: a score with no course-period link cannot reach a
        -- section enrollment and so cannot reach either fact.
        inner join
            {{ ref("stg_focus__gradebook_assignments_join_course_periods") }} as ajcp
            on gg.assignment_id = ajcp.assignment_id
            and gg.course_period_id = ajcp.course_period_id
            and gg.marking_period_id = ajcp.marking_period_id
        inner join
            {{ ref("stg_focus__marking_periods") }} as mp
            on gg.marking_period_id = mp.marking_period_id
        inner join
            {{ ref("int_focus__students") }} as st on gg.student_id = st.student_id
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
