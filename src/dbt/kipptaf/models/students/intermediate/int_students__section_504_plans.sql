with
    plans as (
        select
            student_number,
            _dbt_source_project,
            begin_date,
            end_date,

            if(
                event_selector = 'Currently Valid: Section 504 Plan', true, false
            ) as is_current_plan,
        from {{ ref("stg_edplan__section_504_student_report") }}
        where
            event_selector
            in ('Currently Valid: Section 504 Plan', 'Previous: Section 504 Plan')
            and student_number is not null
    ),

    next_plan as (
        select
            student_number,
            _dbt_source_project,
            begin_date,
            end_date,
            is_current_plan,

            -- false sorts first, so a current plan follows a previous plan
            -- that begins the same day; end_date keeps the later-ending of 2
            -- same-day previous plans
            lead(begin_date) over (
                partition by student_number, _dbt_source_project
                order by begin_date, is_current_plan, end_date
            ) as next_plan_start_date,
        from plans
    ),

    next_plan_bounds as (
        select
            student_number,
            _dbt_source_project,
            begin_date,
            end_date,
            is_current_plan,
            next_plan_start_date,

            date_sub(next_plan_start_date, interval 1 day) as day_before_next_plan,
        from next_plan
    ),

    windows as (
        select
            student_number,
            _dbt_source_project,
            is_current_plan,

            begin_date as plan_start_date,

            case
                when is_current_plan or next_plan_start_date is null
                then coalesce(end_date, cast('9999-12-31' as date))
                when end_date < day_before_next_plan
                then end_date
                else day_before_next_plan
            end as plan_end_date,
        from next_plan_bounds
    )

select
    student_number,
    _dbt_source_project,
    plan_start_date,
    plan_end_date,
    is_current_plan,
from windows
where plan_end_date >= plan_start_date
