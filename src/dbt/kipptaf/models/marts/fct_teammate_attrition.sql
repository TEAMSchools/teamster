with
    teammate_history as (select *, from {{ ref("dim_teammates") }}),

    academic_years as (select distinct academic_year from teammate_history),

    {# any staff not in an inactive status between 9/1 and 4/30 of an academic year #}
    denominator_cohort_ranking as (
        select
            ay.academic_year,
            th.employee_number,
            th.teammate_history_key,
            th.effective_date_start,
            th.effective_date_end,
            row_number() over (
                partition by ay.academic_year, th.employee_number
                order by th.effective_date_start desc
            ) as rn_row,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 4, 30)
            and th.effective_date_end >= date(ay.academic_year, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    denominator_cohort as (select *, from denominator_cohort_ranking where rn_row = 1),

    {# any staff not in terminated or deceased status on 9/1 of the following academic year #}
    returner_cohort as (
        select distinct
            ay.academic_year,
            th.employee_number,
            th.effective_date_start,
            th.effective_date_end,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 9, 1)
            and th.effective_date_end >= date(ay.academic_year + 1, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),
    {# left join to determine returner versus last year roster #}
    final as (
        select
            dc.academic_year,
            dc.employee_number,
            dc.teammate_history_key,
            dc.effective_date_start as effective_date_start_attrition_year,
            dc.effective_date_end as effective_date_end_attrition_year,
            rc.effective_date_start as effective_date_start_next_year,
            rc.effective_date_end as effective_date_end_next_year,
            if(rc.employee_number is null, true, false) as is_attrition
        from denominator_cohort as dc
        left join
            returner_cohort as rc
            on dc.employee_number = rc.employee_number
            and dc.academic_year = rc.academic_year
    )

select *,
from final
