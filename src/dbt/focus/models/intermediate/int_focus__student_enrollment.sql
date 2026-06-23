with
    enrollment as (select *, from {{ ref("stg_focus__student_enrollment") }}),

    schools as (select *, from {{ ref("stg_focus__schools") }}),

    grade_levels as (select *, from {{ ref("stg_focus__school_gradelevels") }}),

    enrollment_codes as (
        select *, from {{ ref("stg_focus__student_enrollment_codes") }}
    )

select
    e.id,
    e.syear,
    e.school_id,
    e.student_id,
    e.grade_id,
    e.enrollment_code,
    e.drop_code,
    e.calendar_id,
    e.start_date,
    e.end_date,

    s.title as school_title,
    s.state_school_id as school_state_school_id,

    g.title as grade_level_title,
    g.short_name as grade_level_short_name,

    ec.title as enrollment_code_title,
    ec.short_name as enrollment_code_short_name,
    ec.type as enrollment_code_type,
from enrollment as e
left join schools as s on e.school_id = s.id
left join grade_levels as g on e.grade_id = g.id
left join enrollment_codes as ec on e.enrollment_code = ec.id
