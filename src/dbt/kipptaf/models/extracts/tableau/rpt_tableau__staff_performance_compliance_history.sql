select
    hd.employee_number as asdf_employee_number,
    hd.adp_associate_id,
    hd.preferred_first_name,
    hd.preferred_last_name,
    hd.current_status as cur,
    hd.termination_date,
    hd.current_legal_entity,
    hd.current_location,
    hd.current_role,
    hd.current_dept,
    hd.race_ethnicity_reporting,
    hd.gender,
    hd.samaccountname,
    hd.current_manager,
    hd.manager_samaccountname,
    hd.academic_year,
    hd.historic_legal_entity,
    hd.historic_location,
    hd.historic_role,
    hd.historic_dept,
    hd.historic_salary,
    hd.pm_term,
    hd.etr_score,
    hd.etr_tier,
    hd.so_score,
    hd.overall_score,
    hd.overall_tier,
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

    hd.most_recent_hire_date as hire_date,
    hd.is_hispanic,
from
    {{ ref("int_people__historic_data_as_of_april30_annually") }} as hd
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
    -- noqa: disable=LT01
    
