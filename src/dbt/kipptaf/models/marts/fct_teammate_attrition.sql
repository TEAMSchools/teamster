with
    teammate_history as (
        select *,
        from {{ ref("dim_teammates") }}
        where
            (job_title != 'Intern' or assignment_status_reason != 'Internship Ended')
            and primary_indicator
    ),

    academic_years as (select distinct academic_year from teammate_history),

    {# latest record for staff not in an inactive status between 9/1 and 4/30 of an academic year #}
    denominator_cohort as (
        select
            ay.academic_year,
            th.employee_number,
            th.teammate_history_key,
            max(th.effective_date_start) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 4, 30)
            and th.effective_date_end >= date(ay.academic_year, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
        group by ay.academic_year, th.employee_number, th.teammate_history_key
    ),

    {# any staff not in terminated or deceased status on 9/1 of the following academic year #}
    returner_cohort as (
        select distinct ay.academic_year, th.employee_number, th.teammate_history_key,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 9, 1)
            and th.effective_date_end >= date(ay.academic_year + 1, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    {# left join to compare prior year to following year rosters #}
    final as (
        select
            dc.academic_year,
            dc.employee_number,
            dc.teammate_history_key,
            if(rc.employee_number is null, true, false) as is_attrition
        from denominator_cohort as dc
        left join
            returner_cohort as rc
            on dc.employee_number = rc.employee_number
            and dc.academic_year = rc.academic_year
    )

select *,
from final
