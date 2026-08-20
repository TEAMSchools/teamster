with
    weekly as (
        select
            student_number,
            academic_year,
            schoolid,
            discipline,
            week_start_monday,

            coalesce(n_lessons_passed_week, 0) as n_lessons_passed_week,
            coalesce(time_on_task_min_week, 0) as time_on_task_min_week,
        from {{ ref("int_topline__iready_lessons_weekly") }}
        /* the weekly source is enrollment-spine-filled through year end, so an
           unbounded count(*) denominator divides by the whole school year for
           any in-progress period -- AY2026 is 96.7% future weeks. Mirrors the
           bound already in int_topline__attendance_period. Note this still
           admits the current partially-elapsed week; that is the same
           partial-window question tracked for the as-of path. */
        where week_start_monday <= current_date('{{ var("local_timezone") }}')
    ),

    periods as (
        select
            schoolid,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,
        from {{ ref("int_topline__periods") }}
        where org_scope = 'school' and period_type != 'week'
    )

select
    w.student_number,
    w.academic_year,
    w.schoolid,
    w.discipline,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    count(*) as week_count,
    sum(w.n_lessons_passed_week) as lessons_passed_sum,
    sum(w.time_on_task_min_week) as time_on_task_min_sum,

    round(
        safe_divide(sum(w.time_on_task_min_week), count(*)), 1
    ) as time_on_task_min_week_avg,

    if(
        safe_divide(sum(w.n_lessons_passed_week), count(*)) >= 2, 1, 0
    ) as meets_lessons_passed_period_int,
from weekly as w
inner join
    periods as p
    on w.schoolid = p.schoolid
    and w.academic_year = p.academic_year
    and w.week_start_monday between p.period_start and p.period_end
group by
    w.student_number,
    w.academic_year,
    w.schoolid,
    w.discipline,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
