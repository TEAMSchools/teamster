with
    unweighted_scale as (
        /* grain projection, not dup-masking: the kipptaf lookup repeats each
           letter once per district with identical points and cutoffs */
        select distinct letter_grade, grade_points, min_cutoffpercentage,
        from {{ ref("int_powerschool__gradescaleitem_lookup") }}
        where gradescale_name = 'KIPP NJ 2019 (5-12) Unweighted'
    ),

    next_rung as (
        select
            p.studentid,
            p.course_number,
            p._dbt_source_project,

            min(us.min_cutoffpercentage) as next_cutoff_percent,
        from {{ ref("int_gpa__course_quarter_pace") }} as p
        inner join
            unweighted_scale as us
            on p.y1_grade_points_unweighted_current < us.grade_points
        where not p.is_locked
        group by p.studentid, p.course_number, p._dbt_source_project
    ),

    scored as (
        select
            p.studentid,
            p.schoolid,
            p.course_number,
            p.course_name,
            p._dbt_source_project,
            p.is_below_target,
            p.is_locked,
            p.potential_credit_hours as credit_hours,

            nr.next_cutoff_percent,

            us.letter_grade as next_letter_grade,
            us.grade_points as next_grade_points,

            p.y1_percent_current as percent_now,
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
        from {{ ref("int_gpa__course_quarter_pace") }} as p
        left join
            next_rung as nr
            on p.studentid = nr.studentid
            and p.course_number = nr.course_number
            and p._dbt_source_project = nr._dbt_source_project
        left join
            unweighted_scale as us on nr.next_cutoff_percent = us.min_cutoffpercentage
    ),

    gapped as (
        select
            *,

            /* the floor keeps a sub-point gap from inflating the score; a gap
               at or below zero means the student is already ahead of the pace
               to the next letter, which is not a win to work on */
            greatest(round(pace_percent_to_next - percent_now, 2), 1.0) as need_gap_raw,

            is_locked
            or next_cutoff_percent is null
            or pace_percent_to_next > 100
            or pace_percent_to_next - percent_now <= 0 as is_disqualified,
        from scored
    ),

    with_score as (
        select
            studentid,
            schoolid,
            course_number,
            course_name,
            _dbt_source_project,
            is_below_target,
            next_letter_grade,
            next_cutoff_percent,
            next_grade_points,
            points_gained,
            pace_percent_to_next,

            if(is_disqualified, null, need_gap_raw) as need_gap,
            if(
                is_disqualified,
                null,
                round(credit_hours * points_gained / need_gap_raw, 2)
            ) as score,
        from gapped
    ),

    ranked as (
        select
            *,

            row_number() over (
                partition by studentid, _dbt_source_project
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
    _dbt_source_project,
    next_letter_grade,
    next_cutoff_percent,
    next_grade_points,
    points_gained,
    pace_percent_to_next,
    need_gap,
    score,

    if(score is null, null, rn) as quickest_win_rank,
from ranked
