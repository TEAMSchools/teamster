with
    history_clean as (
        select
            employee_number,
            assignment_status,
            assignment_status_effective_date as assignment_status_effective_date_start,
            coalesce(job_title, 'Missing Historic Job') as job_title,
            coalesce(
                lead(assignment_status_effective_date, 1) over (
                    partition by employee_number
                    order by assignment_status_effective_date asc
                ),
                work_assignment_termination_date,
                date(9999, 12, 31)
            ) as assignment_status_effective_date_end,
        from {{ ref("base_people__staff_roster_history") }}
    ),

    staff_roster_history as (
        select
            employee_number,
            job_title,
            cast(
                assignment_status_effective_date_start as datetime
            ) as work_assignment_start_date,
            if(
                cast(assignment_status_effective_date_end as datetime)
                >= current_datetime('{{ var("local_timezone") }}'),
                current_datetime('{{ var("local_timezone") }}'),
                cast(assignment_status_effective_date_end as datetime)
            ) as work_assignment_end_date,
            if(
                assignment_status = 'Active', 'days_active', 'days_inactive'
            ) as input_column,
        from history_clean
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
    employee_number,
    years_active_at_kipp,
    years_inactive_at_kipp,
    years_teaching_at_kipp,
    years_active_at_kipp + years_inactive_at_kipp as years_at_kipp_total,
from year_counts
