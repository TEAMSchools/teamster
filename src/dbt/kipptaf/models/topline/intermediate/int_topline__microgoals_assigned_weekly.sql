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

    calendar as (select *, from {{ ref("int_powerschool__calendar_week") }}),

    final as (
        select
            teachers.employee_number,
            teachers.school_id,
            calendar.week_start_monday,
            calendar.week_end_sunday,
            count(distinct microgoals.assignment_id) as microgoals_assigned,
        from teachers
        left join grow_users on teachers.employee_number = grow_users.internal_id_int
        left join microgoals on grow_users.user_id = microgoals.user_id
        left join
            calendar
            on teachers.school_id = calendar.schoolid
            and microgoals.created_date_local
            between calendar.week_start_monday and calendar.week_end_sunday
        group by
            teachers.employee_number,
            teachers.school_id,
            calendar.week_start_monday,
            calendar.week_end_sunday
    )

select *
from final
