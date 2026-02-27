/* PART 1: THE STUDENTS (Actuals) */
select
    r.region,
    r.schoolid,
    r.school,
    r.grade_level,
    r.finalsite_id,
    r.latest_status,

    'Student' as row_type,

    1 as student_count,

    null as seat_target,
    null as fdos_target,

from {{ ref("int_tableau__finalsite_student_scaffold") }} as r
where r.grouped_status = 'Enrolled'

union all

/* PART 2: THE GOALS (Targets) */
select
    gs.region,
    gs.schoolid,
    gs.school,
    gs.grade_level,

    null as finalsite_student_id,

    'Goal Record' as latest_status,
    'Goal' as row_type,

    0 as student_count,

    gs.goal_value as seat_target,

    gf.goal_value as fdos_target,

from {{ ref("stg_google_sheets__finalsite__goals") }} as gs
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as gf
    on gs.schoolid = gf.schoolid
    and gs.grade_level = gf.grade_level
    and gf.goal_name = 'FDOS Target'
where gs.goal_name = 'Seat Target'
