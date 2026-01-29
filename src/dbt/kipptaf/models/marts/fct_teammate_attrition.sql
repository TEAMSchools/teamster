with
    teammate_history as (
        select *,
        from {{ ref("dim_teammates") }}
        where
            (job_title != 'Intern' or assignment_status_reason != 'Internship Ended')
            and primary_indicator
    ),

    academic_years as (
        select distinct employee_number, academic_year, from teammate_history
    ),

    {# Foundation Attrition: latest record for staff not #}
    {#in an inactive status between 9/1 and 4/30 of an academic year #}
    foundation_year_cohort as (
        select
            ay.academic_year,
            th.employee_number,
            max(th.effective_date_start) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 4, 30)
            and th.effective_date_end >= date(ay.academic_year, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
        group by ay.academic_year, th.employee_number
    ),
    {# Foundation Attrition: any staff not in terminated or deceased status #} 
    {# on 9/1 of the following academic year #}
    foundation_returner_cohort as (
        select distinct ay.academic_year, th.employee_number,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 9, 1)
            and th.effective_date_end >= date(ay.academic_year + 1, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    {# New Jersey Compliance Attrition: latest record for staff #}
    {# not in an inactive status between 7/1 and 6/30 of an academic year #}
    nj_year_cohort as (
        select
            ay.academic_year,
            th.employee_number,
            max(th.effective_date_start) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 6, 30)
            and th.effective_date_end >= date(ay.academic_year, 7, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
        group by ay.academic_year, th.employee_number
    ),

    {# New Jersey Compliance  Attrition: any staff not in #}
    {# terminated or deceased status on 7/1 of the following academic year #}
    nj_returner_cohort as (
        select distinct ay.academic_year, th.employee_number,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 7, 1)
            and th.effective_date_end >= date(ay.academic_year + 1, 7, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    {# Recruitment Attrition: latest record for staff not in an #}
    {# inactive status between 9/1 and 8/31 of an academic year #}
    recruitment_year_cohort as (
        select
            ay.academic_year,
            th.employee_number,
            max(th.effective_date_start) as max_effective_date_start,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 8, 31)
            and th.effective_date_end >= date(ay.academic_year, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
        group by ay.academic_year, th.employee_number
    ),

    {# Recruitment Attrition: any staff not in terminated or deceased #}
    {# status on 9/1 of the following academic year #}
    recruitment_returner_cohort as (
        select distinct ay.academic_year, th.employee_number,
        from academic_years as ay
        inner join
            teammate_history as th
            on th.effective_date_start <= date(ay.academic_year + 1, 9, 1)
            and th.effective_date_end >= date(ay.academic_year + 1, 9, 1)
        where th.assignment_status not in ('Pre-Start', 'Terminated', 'Deceased')
    ),

    {# left joins to compare prior year to following year rosters #}
    final as (
        select
            'foundation' as attrition_type,
            fyc.academic_year,
            fyc.employee_number,
            if(frc.employee_number is null, true, false) as is_attrition,
        from foundation_year_cohort as fyc
        left join
            foundation_returner_cohort as frc
            on fyc.employee_number = frc.employee_number
            and fyc.academic_year = frc.academic_year
        union all

        select
            'nj_compliance' as attrition_type,
            njyc.academic_year,
            njyc.employee_number,
            if(njrc.employee_number is null, true, false) as is_attrition,
        from nj_year_cohort as njyc
        left join
            nj_returner_cohort as njrc
            on njyc.employee_number = njrc.employee_number
            and njyc.academic_year = njrc.academic_year
        union all

        select
            'recruitment' as attrition_type,
            ryc.academic_year,
            ryc.employee_number,
            if(rrc.employee_number is null, true, false) as is_attrition,
        from recruitment_year_cohort as ryc
        left join
            recruitment_returner_cohort as rrc
            on ryc.employee_number = rrc.employee_number
            and ryc.academic_year = rrc.academic_year
    )

select *,
from final
