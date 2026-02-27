/* PART 1: THE STUDENTS (Actuals) */
select
    r.aligned_enrollment_academic_year,
    r.region,
    r.schoolid,
    r.school,
    r.finalsite_id,
    r.latest_status,
    r.aligned_enrollment_type as enrollment_type,

    'Student' as row_type,

    1 as student_count,

    null as seat_target,
    null as fdos_target,
    null as budget_target,
    null as new_student_target,
    null as re_enroll_projection,

from {{ ref("int_tableau__finalsite_student_scaffold") }} as r
where r.grouped_status = 'Enrolled'

union all

select
    r.aligned_enrollment_academic_year,
    r.region,
    r.schoolid,
    r.school,
    r.finalsite_id,
    r.latest_status,
    r.enrollment_academic_year_enrollment_type as enrollment_type,

    'Student' as row_type,

    1 as student_count,

    null as seat_target,
    null as fdos_target,
    null as budget_target,
    null as new_student_target,
    null as re_enroll_projection,

from {{ ref("int_tableau__finalsite_student_scaffold") }} as r
where r.grouped_status = 'Enrolled'

union all

/* PART 2: THE GOALS (Targets) */
select
    gs.enrollment_academic_year as aligned_enrollment_academic_year,
    gs.region,
    gs.schoolid,
    gs.school,

    null as finalsite_student_id,

    'Goal Record' as latest_status,
    null as enrollment_type,
    'Goal' as row_type,

    0 as student_count,

    gs.goal_value as seat_target,

    gf.goal_value as fdos_target,

    gb.goal_value as budget_target,

    gn.goal_value as new_student_target,

    ge.goal_value as re_enroll_projection,

from {{ ref("stg_google_sheets__finalsite__goals") }} as gs
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as gf
    on gs.schoolid = gf.schoolid
    and gs.goal_granularity = gf.goal_granularity
    and gf.goal_name = 'FDOS Target'
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as gb
    on gs.schoolid = gb.schoolid
    and gs.goal_granularity = gb.goal_granularity
    and gb.goal_name = 'Budget Target'
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as gn
    on gs.schoolid = gn.schoolid
    and gs.goal_granularity = gn.goal_granularity
    and gn.goal_name = 'New Student Target'
left join
    {{ ref("stg_google_sheets__finalsite__goals") }} as ge
    on gs.schoolid = ge.schoolid
    and gs.goal_granularity = ge.goal_granularity
    and ge.goal_name = 'Re-Enroll Projection'
where gs.goal_name = 'Seat Target' and gs.goal_granularity = 'School'
