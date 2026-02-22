/* PART 1: THE STUDENTS (Actuals) */
select
    'Student' as row_type,
    r.latest_schoolid,
    r.latest_school,
    r.grade_level,
    r.region,
    r.finalsite_student_id,
    r.latest_status,
    1 as student_count,
    null as seat_target,
    null as fdos_target,

    r.last_name || ', ' || r.first_name as student_name,
    case
        when grade_level >= 9
        then 'HS'
        when grade_level >= 5
        then 'MS'
        when grade_level >= 0
        then 'ES'
    end as school_level,
from {{ ref("int_students__finalsite_student_roster") }} as r
where r.latest_status = 'Enrolled'

union all

/* PART 2: THE GOALS (Targets) */
select
    'Goal' as row_type,
    gs.schoolid as latest_schoolid,
    gs.school as latest_school,
    gs.grade_level as grade_level,
    gs.region,
    null as finalsite_student_id,
    'Goal Record' as latest_status,
    0 as student_count,
    gs.goal_value as seat_target,
    gf.goal_value as fdos_target,
    null as student_name,
    gs.school_level,
from {{ ref("stg_google_sheets__finalsite__goals") }} as gs
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as gf
    on gs.schoolid = gf.schoolid
    and gs.grade_level = gf.grade_level
    and gf.goal_name = 'FDOS Target'
where gs.goal_name = 'Seat Target'
