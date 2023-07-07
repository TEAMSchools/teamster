{{ config(enabled=false) }}

with
    elementary_grade as (
        select employee_number, max(student_grade_level) as student_grade_level
        from pm.teacher_grade_levels
        group by employee_number
    ),

    etr_pivot as (
        select df_employee_number, academic_year, pm1, pm2, pm3, pm4
        from
            (
                select df_employee_number, academic_year, pm_term, overall_score
                from pm.teacher_goals_overall_scores_static
                where academic_year >= utilities.global_academic_year() - 1
            ) as sub
            pivot (avg(overall_score) for pm_term in (pm1, pm2, pm3, pm4)) as p
    ),

    itr_pivot as (
        select
            respondent_df_employee_number,
            campaign_academic_year,
            intent_to_return,
            reason_for_leaving_primary,
            reason_for_leaving_secondary,
            transfer_1,
            transfer_oe,
            stay_oe,
            anything_else_oe
        from
            (
                select
                    respondent_df_employee_number,
                    campaign_academic_year,
                    question_shortname,
                    answer
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
    )

select
    c.df_employee_number,
    c.status,
    c.preferred_name,
    c.primary_site,
    c.primary_job,
    c.primary_on_site_department,
    c.mail,
    c.google_email,
    c.original_hire_date,
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
    case
        when
            c.primary_on_site_department = 'Elementary'
            and g.student_grade_level is not null
        then concat(c.primary_on_site_department, ', Grade ', g.student_grade_level)
        else c.primary_on_site_department
    end as department_grade
from {{ ref("base_people__staff_roster") }} as c
left join
    etr_pivot as e
    on c.df_employee_number = e.df_employee_number
    and e.academic_year = utilities.global_academic_year()
left join
    etr_pivot as p
    on c.df_employee_number = p.df_employee_number
    and p.academic_year = utilities.global_academic_year() - 1
left join elementary_grade as g on c.df_employee_number = g.employee_number
left join
    itr_pivot as i
    on c.df_employee_number = i.respondent_df_employee_number
    and i.campaign_academic_year = utilities.global_academic_year()
where c.status not in ('TERMINATED')
