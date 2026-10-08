with
    term_rows as (
        select
            studentid,
            course_number,
            course_name,
            potential_credit_hours,
            courses_gradescaleid_unweighted,
            termbin_end_date,
            termbin_is_current,
            term_weighted_points_possible,
            term_percent_grade_adjusted,
            y1_percent_grade_adjusted,
            y1_grade_points_unweighted,

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
            studentid,
            course_number,
            termbin_is_current,
            term_percent_grade_adjusted,
            y1_percent_grade_adjusted,
            y1_grade_points_unweighted,

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

            max(course_name) as course_name,
            max(potential_credit_hours) as potential_credit_hours,
            max(courses_gradescaleid_unweighted) as courses_gradescaleid_unweighted,
            /* an ended term with no grade is outside the Y1 average PowerSchool
               computes, so it is outside the total too */
            sum(
                if(
                    is_ended and term_percent_grade_adjusted is null,
                    0.0,
                    term_weighted_points_possible
                )
            ) as total_weight,
            sum(
                if(
                    is_ended,
                    term_percent_grade_adjusted * term_weighted_points_possible,
                    0.0
                )
            ) as points_banked,
            sum(if(is_ended, 0.0, term_weighted_points_possible)) as remaining_weight,
            logical_and(is_ended) as is_locked,
        from term_rows
        group by studentid, course_number
    ),

    current_values as (
        select
            studentid,
            course_number,
            y1_percent_grade_adjusted as y1_percent_current,
            y1_grade_points_unweighted as y1_grade_points_unweighted_current,

            if(
                termbin_is_current, term_percent_grade_adjusted, null
            ) as term_percent_current,
        from term_rows_ranked
        where rn_current = 1
    ),

    paced as (
        select
            c.studentid,
            c.course_number,
            c.course_name,
            c.potential_credit_hours,
            c.courses_gradescaleid_unweighted,
            c.total_weight,
            c.points_banked,
            c.remaining_weight,
            c.is_locked,

            cv.y1_percent_current,
            cv.y1_grade_points_unweighted_current,
            cv.term_percent_current,

            t.schoolid,
            t.target_cutoff_percent,

            round(
                safe_divide(
                    t.target_cutoff_percent * c.total_weight - c.points_banked,
                    c.remaining_weight
                ),
                2
            ) as pace_percent,
        from courses as c
        inner join
            current_values as cv
            on c.studentid = cv.studentid
            and c.course_number = cv.course_number
        inner join
            {{ ref("int_powerschool__student_y1_target") }} as t
            on c.studentid = t.studentid
    ),

    pace as (
        select
            studentid,
            schoolid,
            course_number,
            course_name,
            potential_credit_hours,
            courses_gradescaleid_unweighted,
            target_cutoff_percent,
            y1_percent_current,
            y1_grade_points_unweighted_current,
            term_percent_current,
            total_weight,
            points_banked,
            remaining_weight,
            is_locked,

            if(is_locked, null, pace_percent) as pace_percent,

            coalesce(
                y1_percent_current < target_cutoff_percent, false
            ) as is_below_target,
            coalesce(not is_locked and pace_percent <= 50, false) as is_secured,
        from paced
    ),

    unweighted_scale as (
        select letter_grade, grade_points, min_cutoffpercentage,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        where gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted'
    ),

    /* the quickest win: the next letter up in each open course and what it
       costs to reach it by year end */
    next_rung as (
        select
            p.studentid,
            p.course_number,

            min(us.min_cutoffpercentage) as next_cutoff_percent,
        from pace as p
        inner join
            unweighted_scale as us
            on p.y1_grade_points_unweighted_current < us.grade_points
        where not p.is_locked
        group by p.studentid, p.course_number
    ),

    scored as (
        select
            p.studentid,
            p.schoolid,
            p.course_number,
            p.course_name,
            p.potential_credit_hours,
            p.courses_gradescaleid_unweighted,
            p.target_cutoff_percent,
            p.y1_percent_current,
            p.y1_grade_points_unweighted_current,
            p.term_percent_current,
            p.total_weight,
            p.points_banked,
            p.remaining_weight,
            p.is_locked,
            p.pace_percent,
            p.is_below_target,
            p.is_secured,

            nr.next_cutoff_percent,

            us.letter_grade as next_letter_grade,
            us.grade_points as next_grade_points,

            round(
                us.grade_points - p.y1_grade_points_unweighted_current, 2
            ) as points_gained,
            round(
                safe_divide(
                    nr.next_cutoff_percent * p.total_weight - p.points_banked,
                    p.remaining_weight
                ),
                2
            ) as pace_percent_to_next,
        from pace as p
        left join
            next_rung as nr
            on p.studentid = nr.studentid
            and p.course_number = nr.course_number
        left join
            unweighted_scale as us on nr.next_cutoff_percent = us.min_cutoffpercentage
    ),

    gapped as (
        select
            *,

            /* the floor keeps a sub-point gap from inflating the score; a gap
               at or below zero means the student is already ahead of the pace
               to the next letter, which is not a win to work on */
            greatest(
                round(pace_percent_to_next - y1_percent_current, 2), 1.0
            ) as need_gap_raw,

            is_locked
            or next_cutoff_percent is null
            or pace_percent_to_next > 100
            or pace_percent_to_next - y1_percent_current <= 0 as is_disqualified,
        from scored
    ),

    with_score as (
        select
            studentid,
            schoolid,
            course_number,
            course_name,
            potential_credit_hours,
            courses_gradescaleid_unweighted,
            target_cutoff_percent,
            y1_percent_current,
            y1_grade_points_unweighted_current,
            term_percent_current,
            total_weight,
            points_banked,
            remaining_weight,
            is_locked,
            pace_percent,
            is_below_target,
            is_secured,
            next_cutoff_percent,
            next_letter_grade,
            next_grade_points,
            points_gained,
            pace_percent_to_next,

            if(is_disqualified, null, need_gap_raw) as need_gap,
            if(
                is_disqualified,
                null,
                round(potential_credit_hours * points_gained / need_gap_raw, 2)
            ) as score,
        from gapped
    ),

    ranked as (
        select
            *,

            row_number() over (
                partition by studentid
                order by
                    score is null, is_below_target desc, score desc, course_number asc
            ) as rn,
        from with_score
    )

select
    studentid,
    schoolid,
    course_number,
    course_name,
    potential_credit_hours,
    courses_gradescaleid_unweighted,
    target_cutoff_percent,
    y1_percent_current,
    y1_grade_points_unweighted_current,
    term_percent_current,
    total_weight,
    points_banked,
    remaining_weight,
    is_locked,
    pace_percent,
    is_below_target,
    is_secured,
    next_cutoff_percent,
    next_letter_grade,
    next_grade_points,
    points_gained,
    pace_percent_to_next,
    need_gap,
    score,

    if(score is null, null, rn) as quickest_win_rank,
from ranked
