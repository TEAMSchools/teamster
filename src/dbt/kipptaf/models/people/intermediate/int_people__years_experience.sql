with
    staff_roster_history as (
        select
            employee_number,
            job_title,
            work_assignment__fivetran_active,
            primary_indicator,
            coalesce(years_exp_outside_kipp, 0) as years_experience_prior_to_kipp,
            coalesce(years_teaching_in_njfl, 0)
            + coalesce(years_teaching_outside_njfl, 0) as years_teaching_prior_to_kipp,
            cast(
                work_assignment__fivetran_start as datetime
            ) as work_assignment_start_date,
            if
            (
                cast(work_assignment__fivetran_end as datetime)
                >= current_datetime('{{ var("local_timezone") }}'),
                current_datetime('{{ var("local_timezone") }}'),
                cast(work_assignment__fivetran_end as datetime)
            ) as work_assignment_end_date,
            if(
                assignment_status = 'Active', 'days_active', 'days_inactive'
            ) as input_column,
        from {{ ref("base_people__staff_roster_history") }}
        where assignment_status not in ('Terminated', 'Deceased', 'Pre-Start')
    ),

    with_date_diff as (
        select
            employee_number,
            input_column,
            job_title,
            date_diff(
                work_assignment_end_date, work_assignment_start_date, day
            ) as work_assignment_day_count,
        from staff_roster_history
    ),

    day_counts as (
        select
            employee_number,
            input_column,
            sum(work_assignment_day_count) as work_assignment_day_count,
        from with_date_diff
        where job_title != 'Intern'
        group by employee_number, input_column

        union all

        select
            employee_number,
            'days_as_teacher' as input_column,
            sum(work_assignment_day_count) as work_assignment_day_count,
        from with_date_diff
        where
            job_title in (
                'Teacher',
                'Learning Specialist',
                'Learning Specialist Coordinator',
                'Teacher in Residence',
                'Teacher, ESL',
                'Teacher ESL',
                'Co-Teacher'
            )
        group by employee_number
    ),

    day_count_pivot as (
        select
            employee_number,
            coalesce(days_active, 0) as days_active,
            coalesce(days_inactive, 0) as days_inactive,
            coalesce(days_as_teacher, 0) as days_as_teacher,
        from
            day_counts pivot (
                max(work_assignment_day_count) for input_column
                in ('days_active', 'days_inactive', 'days_as_teacher')
            )
    ),

    year_counts as (
        select
            *,
            round(days_active / 365.25, 2) as years_active_at_kipp,
            round(days_inactive / 365.25, 2) as years_inactive_at_kipp,
            round(days_as_teacher / 365.25, 2) as years_teaching_at_kipp,
        from day_count_pivot
    )

select
    sr.employee_number,
    coalesce(sr.years_exp_outside_kipp, 0) as years_experience_prior_to_kipp,
    coalesce(sr.years_teaching_in_njfl, 0)
    + coalesce(sr.years_teaching_outside_njfl, 0) as years_teaching_prior_to_kipp,
    sr.assignment_status as current_position_status,

    yc.years_active_at_kipp,
    yc.years_inactive_at_kipp,
    yc.years_teaching_at_kipp,
    yc.years_active_at_kipp + yc.years_inactive_at_kipp as years_at_kipp_total,

    yc.years_teaching_at_kipp
    + coalesce(sr.years_teaching_in_njfl, 0)
    + coalesce(sr.years_teaching_outside_njfl, 0) as years_teaching_total,

    yc.years_active_at_kipp
    + years_inactive_at_kipp
    + coalesce(sr.years_exp_outside_kipp, 0) as years_experience_total,
from {{ ref("base_people__staff_roster") }} as sr
left join year_counts as yc on sr.employee_number = yc.employee_number
