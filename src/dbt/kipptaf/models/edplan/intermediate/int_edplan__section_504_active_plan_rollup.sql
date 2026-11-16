with
    events as (
        select
            student_number,
            _dbt_source_project,

            if(
                event_selector = 'Currently Valid: Section 504 Plan'
                and (
                    end_date is null
                    or end_date >= current_date('{{ var("local_timezone") }}')
                ),
                true,
                false
            ) as is_active_504_plan,
        from {{ ref("stg_edplan__section_504_student_report") }}
    )

select student_number, _dbt_source_project, count(*) as n_active_504_plans,
from events
where is_active_504_plan
group by student_number, _dbt_source_project
