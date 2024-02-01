with
    elementary_grade as (
        select teachernumber, max(grade_level) as max_grade_level,
        from {{ ref("int_powerschool__teacher_grade_levels") }}
        where academic_year = {{ var("current_academic_year") }}
        group by teachernumber
    )

{#- etr_pivot as (
        select df_employee_number, academic_year, pm1, pm2, pm3, pm4
        from
            (
                select df_employee_number, academic_year, pm_term, overall_score
                from pm.teacher_goals_overall_scores_static
                where academic_year >= utilities.global_academic_year() - 1
            ) as sub
            pivot (avg(overall_score) for pm_term in (pm1, pm2, pm3, pm4)) as p
    ), #}
{#- itr_pivot as (
        select
            respondent_df_employee_number,
            campaign_academic_year,
            intent_to_return,
            reason_for_leaving_primary,
            reason_for_leaving_secondary,
            transfer_1,
            transfer_oe,
            stay_oe,
            anything_else_oe,
        from
            (
                select
                    respondent_df_employee_number,
                    campaign_academic_year,
                    question_shortname,
                    answer,
                from surveys.intent_to_return_survey_detail
            ) as sub pivot (
                max(answer) for question_shortname in (
                    intent_to_return,
                    reason_for_leaving_primary,
                    reason_for_leaving_secondary,
                    transfer_1,
                    transfer_oe,
                    stay_oe,
                    anything_else_oe
                )
            ) as p
    ) #}
select
    c.employee_number as df_employee_number,
    if(c.is_prestart, 'Pre-Start', c.assignment_status) as `status`,
    c.preferred_name_lastfirst as preferred_name,
    c.home_work_location_name as primary_site,
    c.job_title as primary_job,
    c.department_home_name as primary_on_site_department,
    c.mail,
    c.google_email,
    c.worker_original_hire_date as original_hire_date,
    c.business_unit_home_name as entity,

    null as pm1,
    null as pm2,
    null as pm3,
    -- TODO: rename
    null as `last year final`,  -- noqa: RF05
    null as intent_to_return,
    null as reason_for_leaving_primary,
    null as reason_for_leaving_secondary,
    null as transfer_1,
    null as transfer_oe,
    null as stay_oe,
    null as anything_else_oe,
    {#-
    round(e.pm1, 2) as pm1,
    round(e.pm2, 2) as pm2,
    round(e.pm3, 2) as pm3,
    round(p.pm4, 2) as [last year final],
    i.intent_to_return,
    i.reason_for_leaving_primary,
    i.reason_for_leaving_secondary,
    i.transfer_1,
    i.transfer_oe,
    i.stay_oe,
    i.anything_else_oe,
    #}
    if(
        c.department_home_name = 'Elementary' and g.max_grade_level is not null,
        concat(c.department_home_name, ', Grade ', g.max_grade_level),
        c.department_home_name
    ) as department_grade,
from {{ ref("base_people__staff_roster") }} as c
left join elementary_grade as g on c.powerschool_teacher_number = g.teachernumber
{#- left join
    itr_pivot as i
    on c.df_employee_number = i.respondent_df_employee_number
    and i.campaign_academic_year = utilities.global_academic_year() #}
{#-
left join
    etr_pivot as e
    on c.df_employee_number = e.df_employee_number
    and e.academic_year = utilities.global_academic_year()
left join
    etr_pivot as p
    on c.df_employee_number = p.df_employee_number
    and p.academic_year = utilities.global_academic_year() - 1
    #}
where c.assignment_status not in ('Terminated')
