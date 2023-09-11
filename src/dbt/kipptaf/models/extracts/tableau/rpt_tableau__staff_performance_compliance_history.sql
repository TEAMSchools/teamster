with
    years as (
        select
            extract(year from date_day) as academic_year,
            if(
                extract(year from date_day) = {{ var("current_academic_year") }},
                current_date('{{ var("local_timezone") }}'),
                date((extract(year from date_day) + 1), 6, 30)
            ) as effective_date,
        from {{ ref("utils__date_spine") }}
        where extract(month from date_day) = 7 and extract(day from date_day) = 1
    )
{# ,

    cert_history as (
        select c.employee_number, y.academic_year, count(c.certificate_type) as n_certs
        from people.certification_history as c
        inner join years as y on (y.effective_date > c.issued_date)
        where c.valid_cert = 1
        group by c.employee_number, y.academic_year
    )
#}
select
    s.employee_number as asdf_employee_number,
    s.worker_id as adp_associate_id,
    s.preferred_name_given_name as preferred_first_name,
    s.preferred_name_family_name as preferred_last_name,
    s.assignment_status as cur,
    s.worker_termination_date as termination_date,
    s.business_unit_home_name as current_legal_entity,
    s.home_work_location_name as current_location,
    s.job_title as current_role,
    s.department_home_name as current_dept,
    s.ethnicity_long_name as primary_ethnicity,
    s.gender_long_name as gender,
    s.sam_account_name as samaccountname,
    s.report_to_preferred_name_lastfirst as current_manager,
    s.report_to_sam_account_name as manager_samaccountname,
    ifnull(s.worker_rehire_date, s.worker_original_hire_date) as hire_date,
    if(s.ethnicity_long_name = 'Hispanic or Latino', true, false) as is_hispanic,

    y.academic_year,

    e.business_unit_home_name as historic_legal_entity,
    e.home_work_location_name as historic_location,
    e.job_title as historic_role,
    e.department_home_name as historic_dept,
    e.base_remuneration_annual_rate_amount_amount_value as historic_salary,

    null as pm_term,

    null as etr_score,
    null as etr_tier,
    null as so_score,
    null as overall_score,
    null as overall_tier,

    {#
    case when c.n_certs > 0 then 1 else 0 end as is_certified,
    #}
    null as is_certified,

    {#
    a.absenses_approved as ay_approved_absences,
    a.absenses_unapproved as ay_unapproved_absences,
    a.late_tardy_approved as ay_approved_tardies,
    a.late_tardy_unapproved as ay_unapproved_tardies,
    a.left_early_approved as ay_approved_left_early,
    a.left_early_unapproved as ay_unapproved_left_early,
    #}
    null as ay_approved_absences,
    null as ay_unapproved_absences,
    null as ay_approved_tardies,
    null as ay_unapproved_tardies,
    null as ay_approved_left_early,
    null as ay_unapproved_left_early,
from {{ ref("base_people__staff_roster") }} as s
inner join
    years as y
    on y.effective_date between s.worker_original_hire_date and coalesce(
        s.worker_termination_date, date(9999, 12, 31)
    )
left join
    {{ ref("base_people__staff_roster_history") }} as e
    on s.employee_number = e.employee_number
    and y.effective_date
    between cast(e.work_assignment__fivetran_start as date) and cast(
        e.work_assignment__fivetran_end as date
    )
    and e.primary_indicator
    and e.job_title is not null
    and e.assignment_status not in ('Terminated', 'Deceased')
    {#
inner join pm.teacher_goals_term_map as tm
    on y.academic_year = tm.academic_year
    and tm.metric_name = 'etr_overall_score'
#}
    {#
left join
    pm.teacher_goals_overall_scores_static as pm
    on s.df_employee_number = pm.df_employee_number
    and y.academic_year = pm.academic_year
    and tm.pm_term = pm.pm_term
#}
    {#
left join
    cert_history as c
    on s.df_employee_number = c.employee_number
    and y.academic_year = c.academic_year
#}
    {#
left join
    people.staff_attendance_rollup as a
    on s.df_employee_number = a.df_employee_number
    and y.academic_year = a.academic_year
#}
    
