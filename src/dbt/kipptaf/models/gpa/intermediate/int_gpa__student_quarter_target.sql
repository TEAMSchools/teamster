with
    unweighted_scale as (
        /* grain projection, not dup-masking: the kipptaf lookup repeats each
           letter once per district with identical points and cutoffs */
        select distinct letter_grade, grade_points, min_cutoffpercentage,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        /* every scale in use shares these cutoffs; 2019 Unweighted is the
           reference, and the 83 floor is the B cutoff */
        where
            gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted'
            and min_cutoffpercentage >= 83
    ),

    /* one row per current-year GPA course; final_grades is one row per course
       and termbin */
    courses as (
        select
            studentid,
            course_number,
            _dbt_source_project,

            max(potential_credit_hours) as credits,
            max(y1_percent_grade_adjusted) as y1_percent,
            max(y1_grade_points_unweighted) as y1_points_unweighted,
            max(
                case
                    courses_gradescaleid when 991 then 1.0 when 1075 then 0.5 else 0.0
                end
            ) as bump,
            logical_and(
                termbin_end_date < current_date('{{ var("local_timezone") }}')
            ) as is_locked,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and exclude_from_gpa = 0
            and not is_dropped_section
            and potential_credit_hours > 0
        group by studentid, course_number, _dbt_source_project
    ),

    schedule as (
        select
            studentid,
            _dbt_source_project,

            sum(credits) as gpa_credits,
            sum(credits * bump) as bump_points,
            countif(not is_locked) as n_courses_unlocked,
            sum(if(is_locked, 0.0, credits)) as unlocked_credits,
            /* a locked course with no live Y1 counts nowhere, as in the Y1
               average PowerSchool computes */
            sum(
                if(
                    is_locked and y1_points_unweighted is not null,
                    credits * y1_points_unweighted,
                    0.0
                )
            ) as locked_points,
            sum(
                if(is_locked and y1_points_unweighted is not null, credits, 0.0)
            ) as locked_credits,
        from courses
        group by studentid, _dbt_source_project
    ),

    students as (
        select
            co.studentid,
            co.schoolid,
            co.student_number,
            co._dbt_source_project,

            gc.is_cumulative_3_0_attainable,
            gc.cumulative_y1_gpa_projected_unweighted,

            s.n_courses_unlocked,

            safe_divide(s.bump_points, s.gpa_credits) as schedule_bump,

            /* the Monitor's need times its credit base is the constant
               3.0 x (prior + current credits) - prior points. Re-base it on
               every scheduled course, then take out the locked courses at
               their live points and solve over the open credits */
            safe_divide(
                round(gc.gpa_needed_for_cumulative_3_0, 4)
                * gc.potential_gpa_credits_current_year
                + 3.0
                * (
                    s.locked_credits
                    + s.unlocked_credits
                    - gc.potential_gpa_credits_current_year
                )
                - s.locked_points,
                s.unlocked_credits
            ) as gpa_needed_raw,
        from {{ ref("int_extracts__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on co.studentid = gc.studentid
            and co.schoolid = gc.schoolid
            and co._dbt_source_project = gc._dbt_source_project
        left join
            schedule as s
            on co.studentid = s.studentid
            and co._dbt_source_project = s._dbt_source_project
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and co.school_level = 'HS'
    ),

    students_rounded as (
        select *, round(gpa_needed_raw, 4) as gpa_needed_unweighted, from students
    ),

    targets as (
        select
            st.studentid,
            st.schoolid,
            st._dbt_source_project,

            min(us.min_cutoffpercentage) as target_cutoff_percent,
        from students_rounded as st
        inner join unweighted_scale as us on st.gpa_needed_unweighted <= us.grade_points
        group by st.studentid, st.schoolid, st._dbt_source_project
    ),

    with_target as (
        select
            st.studentid,
            st.schoolid,
            st.student_number,
            st._dbt_source_project,
            st.gpa_needed_unweighted,
            st.is_cumulative_3_0_attainable,
            st.cumulative_y1_gpa_projected_unweighted,
            st.n_courses_unlocked,

            t.target_cutoff_percent,

            us.letter_grade as target_letter_grade,
            us.grade_points as target_grade_points,

            coalesce(st.schedule_bump, 0.0) as schedule_bump,
        from students_rounded as st
        left join
            targets as t
            on st.studentid = t.studentid
            and st.schoolid = t.schoolid
            and st._dbt_source_project = t._dbt_source_project
        left join
            unweighted_scale as us on t.target_cutoff_percent = us.min_cutoffpercentage
    ),

    below_target as (
        select
            wt.studentid,
            wt.schoolid,
            wt._dbt_source_project,

            countif(c.y1_percent < wt.target_cutoff_percent) as n_courses_below_target,
            countif(c.y1_percent is null) as n_courses_ungraded,
        from with_target as wt
        inner join
            courses as c
            on wt.studentid = c.studentid
            and wt._dbt_source_project = c._dbt_source_project
        where not c.is_locked
        group by wt.studentid, wt.schoolid, wt._dbt_source_project
    )

select
    wt.studentid,
    wt.schoolid,
    wt.student_number,
    wt._dbt_source_project,
    wt.gpa_needed_unweighted,
    wt.target_cutoff_percent,
    wt.target_letter_grade,
    wt.target_grade_points,
    wt.is_cumulative_3_0_attainable,
    wt.cumulative_y1_gpa_projected_unweighted,

    coalesce(wt.n_courses_unlocked, 0) as n_courses_unlocked,
    coalesce(bt.n_courses_below_target, 0) as n_courses_below_target,
    round(wt.schedule_bump, 4) as schedule_bump,
    round(wt.gpa_needed_unweighted + wt.schedule_bump, 2) as gpa_needed_weighted,

    case
        when wt.gpa_needed_unweighted is null or wt.is_cumulative_3_0_attainable is null
        then 'unknown'
        when not wt.is_cumulative_3_0_attainable or wt.target_cutoff_percent is null
        then 'goal_not_attainable'
        when wt.cumulative_y1_gpa_projected_unweighted >= 3.0
        then 'on_pace'
        when
            wt.n_courses_unlocked > 0
            and bt.n_courses_ungraded = 0
            and bt.n_courses_below_target = 0
        then 'on_pace'
        else 'not_on_pace'
    end as pace_status,
from with_target as wt
left join
    below_target as bt
    on wt.studentid = bt.studentid
    and wt.schoolid = bt.schoolid
    and wt._dbt_source_project = bt._dbt_source_project
