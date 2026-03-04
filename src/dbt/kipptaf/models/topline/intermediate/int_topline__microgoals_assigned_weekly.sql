with
    teachers as (
        select
            employee_number,
            home_work_location_powerschool_school_id as school_id,
            effective_date_start,
            effective_date_end,
        from {{ ref("int_people__staff_roster_history") }}
        where
            primary_indicator
            and assignment_status = 'Active'
            and job_title in (
                'Teacher',
                'Teacher in Residence',
                'ESE Teacher',
                'Learning Specialist',
                'Teacher ESL',
                'Teacher in Residence ESL'
            )
    ),

    grow_users as (
        select user_id, internal_id_int, from {{ ref("stg_schoolmint_grow__users") }}
    ),

    microgoals as (
        select user_id, assignment_id, created_date_local,
        from {{ ref("stg_schoolmint_grow__assignments") }}
    ),

    calendar as (
        select schoolid, academic_year, week_start_monday, week_end_sunday,
        from {{ ref("int_powerschool__calendar_week") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    t.employee_number,
    t.school_id,

    cal.academic_year,
    cal.week_start_monday,
    cal.week_end_sunday,

    count(distinct m.assignment_id) as microgoals_assigned,
from teachers as t
inner join
    calendar as cal
    on t.school_id = cal.schoolid
    /* if a teacher switches schools mid-week, they will be counted in the receiving
    school only for that week */
    and cal.week_end_sunday between t.effective_date_start and t.effective_date_end
inner join grow_users as u on t.employee_number = u.internal_id_int
left join
    microgoals as m
    on u.user_id = m.user_id
    and m.created_date_local between cal.week_start_monday and cal.week_end_sunday
group by
    t.employee_number,
    t.school_id,
    cal.academic_year,
    cal.week_start_monday,
    cal.week_end_sunday
