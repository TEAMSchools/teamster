with
    staff_roster_history_distinct as (
        select distinct
            employee_number,
            assignment_status,
            assignment_status_effective_date,
            work_assignment_termination_date,

            coalesce(job_title, 'Missing Historic Job') as job_title,
            if(
                assignment_status = 'Active', 'days_active', 'days_inactive'
            ) as input_column,
        from {{ ref("base_people__staff_roster_history") }}
    ),

    with_end_date as (
        select
            employee_number,
            assignment_status,
            job_title,
            input_column,
            assignment_status_effective_date as assignment_status_effective_date_start,

            coalesce(
                date_sub(
                    lead(assignment_status_effective_date, 1) over (
                        partition by employee_number
                        order by assignment_status_effective_date asc
                    ),
                    interval 1 day
                ),
                work_assignment_termination_date,
                date(9999, 12, 31)
            ) as assignment_status_effective_date_end,
        from staff_roster_history_distinct
    ),

    with_end_date_corrected as (
        select
            employee_number,
            job_title,
            assignment_status_effective_date_start,
            input_column,

            if(
                assignment_status_effective_date_end
                >= current_date('{{ var("local_timezone") }}'),
                current_date('{{ var("local_timezone") }}'),
                assignment_status_effective_date_end
            ) as assignment_status_effective_date_end,
        from with_end_date
        where
            assignment_status not in ('Terminated', 'Deceased', 'Pre-Start')
            and job_title != 'Intern'
            and assignment_status_effective_date_end
            >= assignment_status_effective_date_start
    ),

    with_year_scaffold as (
        select
            srh.employee_number,
            srh.job_title,
            srh.input_column,

            d as date_value,
            {{
                teamster_utils.date_to_fiscal_year(
                    date_field="d", start_month=7, year_source="start"
                )
            }} as academic_year,
        from with_end_date_corrected as srh
        inner join
            unnest(
                array(
                    select *,
                    from
                        unnest(
                            generate_date_array(
                                srh.assignment_status_effective_date_start,
                                srh.assignment_status_effective_date_end
                            )
                        )
                )
            ) as d
    ),

    with_ay_dates as (
        select
            employee_number,
            academic_year,
            job_title,
            input_column,
            min(date_value) as academic_year_start_date,
            max(date_value) as academic_year_end_date,
        from with_year_scaffold
        group by employee_number, academic_year, job_title, input_column
    ),

    with_date_diff as (
        select
            employee_number,
            academic_year,
            job_title,
            input_column,

            date_diff(
                academic_year_end_date, academic_year_start_date, day
            ) as work_assignment_day_count,
        from with_ay_dates
    ),

    day_counts as (
        select
            employee_number,
            academic_year,
            job_title,
            input_column,
            sum(work_assignment_day_count) as work_assignment_day_count,
        from with_date_diff
        group by employee_number, academic_year, job_title, input_column

        union all

        select
            employee_number,
            academic_year,
            job_title,
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
        group by employee_number, academic_year, job_title
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
