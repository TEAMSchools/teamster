with
    school_year_bounds as (
        select
            schoolid,
            _dbt_source_project,
            academic_year,

            min(date_value) as year_first_in_session,
            max(date_value) as year_last_in_session,
        from {{ ref("int_students__calendar_day") }}
        where insession = 1
        group by schoolid, _dbt_source_project, academic_year
    ),

    -- exitdate is exclusive: a stint's exitdate equals the next stint's
    -- entrydate, so the last enrolled day is the day before it.
    stint_bounds as (
        select
            student_number,
            _dbt_source_project,
            academic_year,
            entrydate,
            exitdate,
            schoolid,
            grade_level,
            enroll_status,

            date_sub(exitdate, interval 1 day) as stint_last_day,
        from {{ ref("int_extracts__student_enrollments") }}
        where entrydate is not null
    ),

    -- dim_dates runs to 9999-12-31. Every day past today is unreachable --
    -- window_end is itself capped at today -- so filtering here cuts the range
    -- join's right side from 2.9M rows to a few thousand. Without it the join
    -- exceeds BigQuery's on-demand CPU-to-bytes ratio and the query is refused.
    calendar_spine as (
        select date_key,
        from {{ ref("dim_dates") }}
        where date_key <= current_date('{{ var("local_timezone") }}')
    ),

    enrollment_windows as (
        select
            s.student_number,
            s._dbt_source_project,
            s.academic_year,
            s.entrydate,
            s.schoolid,
            s.grade_level,
            s.enroll_status,

            greatest(s.entrydate, b.year_first_in_session) as window_start,

            least(
                coalesce(s.stint_last_day, b.year_last_in_session),
                b.year_last_in_session,
                current_date('{{ var("local_timezone") }}')
            ) as window_end,
        from stint_bounds as s
        inner join
            school_year_bounds as b
            on s.schoolid = b.schoolid
            and s._dbt_source_project = b._dbt_source_project
            and s.academic_year = b.academic_year
    )

select
    w.student_number,
    w._dbt_source_project,
    w.academic_year,
    w.entrydate,
    w.schoolid,
    w.grade_level,
    w.enroll_status,

    d.date_key as calendardate,

    cd.week_start_date,
    cd.week_end_date,

    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,

    t.term,
    t.semester,

    w.academic_year - 1990 as yearid,

    coalesce(cd.is_in_session, false) as is_in_session_day,

    if(
        coalesce(cd.is_in_session, false),
        coalesce(cd.membershipvalue, cast(0 as float64)),
        cast(0 as float64)
    ) as membershipvalue,
from enrollment_windows as w
inner join
    calendar_spine as d on w.window_start <= d.date_key and w.window_end >= d.date_key
left join
    {{ ref("int_students__calendar_day") }} as cd
    on w.schoolid = cd.schoolid
    and w._dbt_source_project = cd._dbt_source_project
    and d.date_key = cd.date_value
left join
    {{ ref("int_students__calendar_week") }} as cw
    on w.schoolid = cw.schoolid
    and w._dbt_source_project = cw._dbt_source_project
    and d.date_key between cw.week_start_monday and cw.week_end_sunday
left join
    {{ ref("int_students__terms") }} as t
    on w.schoolid = t.schoolid
    and w._dbt_source_project = t._dbt_source_project
    and d.date_key between t.term_start_date and t.term_end_date
    and t.term is not null
