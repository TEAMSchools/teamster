with
    unweighted_scale as (
        select letter_grade, grade_points, min_cutoffpercentage,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        /* the reference scale; the 83 floor is the B cutoff */
        where
            gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted'
            and min_cutoffpercentage >= 83
    ),

    scale_names as (
        select gradescaleid, gradescale_name,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        group by gradescaleid, gradescale_name
    ),

    /* final_grades is one row per course and termbin, and its Y1 columns are
       running year-to-date values that differ from term to term. The current
       Y1 is the one on the current or latest-started term row, ranked the
       same way as int_powerschool__course_pace */
    term_rows as (
        select
            studentid,
            course_number,
            potential_credit_hours,
            courses_gradescaleid_unweighted,
            y1_percent_grade_adjusted,
            y1_grade_points_unweighted,
            termbin_end_date,
            termbin_is_current,

            /* scale ids and bump sizes mirror base_powerschool__sections */
            case
                courses_gradescaleid when 991 then 1.0 when 1075 then 0.5 else 0.0
            end as bump,

            termbin_end_date < current_date('{{ var("local_timezone") }}') as is_ended,
            termbin_start_date
            <= current_date('{{ var("local_timezone") }}') as is_started,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and exclude_from_gpa = 0
            and not is_dropped_section
            and potential_credit_hours > 0
    ),

    term_rows_ranked as (
        select
            *,

            row_number() over (
                partition by studentid, course_number
                order by termbin_is_current desc, is_started desc, termbin_end_date desc
            ) as rn_current,
        from term_rows
    ),

    courses as (
        select
            studentid,
            course_number,

            max(potential_credit_hours) as credits,
            max(bump) as bump,
            max(courses_gradescaleid_unweighted) as courses_gradescaleid_unweighted,
            max(if(rn_current = 1, y1_percent_grade_adjusted, null)) as y1_percent,
            max(
                if(rn_current = 1, y1_grade_points_unweighted, null)
            ) as y1_points_unweighted,
            logical_and(is_ended) as is_locked,
            logical_or(is_started) as is_started,
        from term_rows_ranked
        group by studentid, course_number
    ),

    courses_with_scale as (
        select
            c.studentid,
            c.course_number,
            c.credits,
            c.bump,
            c.y1_percent,
            c.y1_points_unweighted,
            c.is_locked,
            c.is_started,

            /* a course on any other scale, or one the lookup cannot resolve,
               cannot be read on the reference cutoffs */
            coalesce(
                sn.gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted', false
            ) as is_reference_scale,
        from courses as c
        left join
            scale_names as sn on c.courses_gradescaleid_unweighted = sn.gradescaleid
    ),

    schedule as (
        select
            studentid,

            countif(not is_locked) as n_courses_unlocked,
            countif(
                not is_locked and not is_reference_scale
            ) as n_courses_unknown_scale,
            sum(if(is_locked, 0.0, credits)) as unlocked_credits,
            sum(if(is_locked, 0.0, credits * bump)) as unlocked_bump_points,
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
        from courses_with_scale
        group by studentid
    ),

    students as (
        select
            co.studentid,
            co.schoolid,

            gc.students_student_number as student_number,
            gc.is_cumulative_3_0_attainable,
            gc.cumulative_y1_gpa_projected_unweighted,

            s.n_courses_unlocked,
            s.n_courses_unknown_scale,

            /* the bonus is averaged over the same open credits the need is
               averaged over, so the two add */
            safe_divide(s.unlocked_bump_points, s.unlocked_credits) as schedule_bump,

            /* the Monitor's need times its credit base is the constant
               3.0 x (prior + current credits) - prior points. Re-base it on
               every scheduled course, then take out the locked courses at
               their live points and solve over the open credits */
            safe_divide(
                gc.gpa_needed_for_cumulative_3_0 * gc.potential_gpa_credits_current_year
                + 3.0
                * (
                    s.locked_credits
                    + s.unlocked_credits
                    - gc.potential_gpa_credits_current_year
                )
                - s.locked_points,
                s.unlocked_credits
            ) as gpa_needed_raw,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_powerschool__gpa_cumulative") }} as gc
            on co.studentid = gc.studentid
            and co.schoolid = gc.schoolid
        left join schedule as s on co.studentid = s.studentid
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

            min(us.min_cutoffpercentage) as target_cutoff_percent,
        from students_rounded as st
        inner join unweighted_scale as us on st.gpa_needed_unweighted <= us.grade_points
        group by st.studentid, st.schoolid
    ),

    with_target as (
        select
            st.studentid,
            st.schoolid,
            st.student_number,
            st.gpa_needed_unweighted,
            st.is_cumulative_3_0_attainable,
            st.cumulative_y1_gpa_projected_unweighted,
            st.n_courses_unlocked,
            st.n_courses_unknown_scale,

            t.target_cutoff_percent,

            us.letter_grade as target_letter_grade,
            us.grade_points as target_grade_points,

            coalesce(st.schedule_bump, 0.0) as schedule_bump,
        from students_rounded as st
        left join
            targets as t on st.studentid = t.studentid and st.schoolid = t.schoolid
        left join
            unweighted_scale as us on t.target_cutoff_percent = us.min_cutoffpercentage
    ),

    below_target as (
        select
            wt.studentid,
            wt.schoolid,

            countif(c.y1_percent < wt.target_cutoff_percent) as n_courses_below_target,
            /* a course that has not started yet has no grade to be missing */
            countif(c.is_started and c.y1_percent is null) as n_courses_ungraded,
        from with_target as wt
        inner join courses_with_scale as c on wt.studentid = c.studentid
        where not c.is_locked
        group by wt.studentid, wt.schoolid
    ),

    with_status as (
        select
            wt.studentid,
            wt.schoolid,
            wt.student_number,
            wt.gpa_needed_unweighted,
            wt.target_cutoff_percent,
            wt.target_letter_grade,
            wt.target_grade_points,
            wt.is_cumulative_3_0_attainable,
            wt.cumulative_y1_gpa_projected_unweighted,
            wt.schedule_bump,

            coalesce(wt.n_courses_unlocked, 0) as n_courses_unlocked,
            coalesce(bt.n_courses_below_target, 0) as n_courses_below_target,

            case
                when
                    wt.gpa_needed_unweighted is null
                    or wt.is_cumulative_3_0_attainable is null
                    or wt.n_courses_unknown_scale > 0
                then 'unknown'
                /* the re-solved need decides, not the Monitor's flag, which
                   counts only the courses already started (#5756) and so reads
                   false for students whose full schedule can still reach 3.0 */
                when wt.target_cutoff_percent is null
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
    )

select
    studentid,
    schoolid,
    student_number,
    is_cumulative_3_0_attainable,
    cumulative_y1_gpa_projected_unweighted,
    n_courses_unlocked,
    pace_status,

    round(schedule_bump, 4) as schedule_bump,

    /* an unknown status carries no numbers: a course on another scale could
       make every one of them a wrong letter */
    if(pace_status = 'unknown', 0, n_courses_below_target) as n_courses_below_target,
    if(pace_status = 'unknown', null, gpa_needed_unweighted) as gpa_needed_unweighted,
    if(pace_status = 'unknown', null, target_cutoff_percent) as target_cutoff_percent,
    if(pace_status = 'unknown', null, target_letter_grade) as target_letter_grade,
    if(pace_status = 'unknown', null, target_grade_points) as target_grade_points,
    if(
        pace_status = 'unknown', null, round(gpa_needed_unweighted + schedule_bump, 2)
    ) as gpa_needed_weighted,
from with_status
