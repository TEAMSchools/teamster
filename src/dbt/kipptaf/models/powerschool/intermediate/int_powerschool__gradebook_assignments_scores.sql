with
    scores as (
        select
            a.sectionsdcid,
            a.assignmentid,
            a.name as assignment_name,
            a.duedate,
            a.scoretype,
            a.totalpointvalue,
            a.category_name,
            a.category_code,
            a.iscountedinfinalgrade,

            s.scorepoints,
            s.actualscoreentered,

            coalesce(s.islate, 0) as is_late,
            coalesce(s.isexempt, 0) as is_exempt,
            coalesce(s.ismissing, 0) as is_missing,

            if(
                coalesce(s.isexempt, 0) = 0 or a.iscountedinfinalgrade = 1, true, false
            ) as is_expected,

            if(
                a.scoretype = 'POINTS',
                s.scorepoints,
                safe_cast(s.actualscoreentered as numeric)
            ) as score_entered,

            if(
                a.scoretype = 'POINTS',
                round(safe_divide(s.scorepoints, a.totalpointvalue) * 100, 2),
                safe_cast(s.actualscoreentered as numeric)
            ) as assign_final_score_percent,

        from {{ ref("int_powerschool__gradebook_assignments") }} as a
        /* PS automatically assigns ALL assignments to a student when they enroll into
        a section, including those from before their enrollment date. This join ensures
        assignments are only matched to valid student enrollments */
        inner join
            {{ ref("base_powerschool__course_enrollments") }} as e
            on a.sectionsdcid = e.sections_dcid
            and a.duedate >= e.cc_dateenrolled
            and {{ union_dataset_join_clause(left_alias="a", right_alias="e") }}
            and not e.is_dropped_section
        left join
            {{ ref("stg_powerschool__assignmentscore") }} as s
            on a.assignmentsectionid = s.assignmentsectionid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
            and e.students_dcid = s.studentsdcid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}

    )

select
    *,

    if(is_expected and score_entered is not null, true, false) as is_expected_scored,

    if(score_entered = 0 and is_expected, 1, 0) as is_zero,

    if(score_entered is null and is_expected, 1, 0) as is_null,

from scores
