with
    response_identifiers as (
        select
            fr.survey_id,
            fr.survey_title,
            fr.survey_response_id,
            fr.date_started,
            fr.date_submitted,
            fr.respondent_email,
            fr.respondent_employee_number,
            fr.respondent_preferred_name,
            fr.respondent_samaccountname,
            fr.respondent_userprincipalname,
            fr.academic_year as campaign_academic_year,
            fr.term_name as campaign_name,
            fr.term_code as campaign_reporting_term,
            fr.question_title,
            fr.question_shortname,
            fr.answer,

            ra.approval_level,

            safe_cast(
                regexp_extract(fr.answer, r'\((\d{6})\)') as integer
            ) as subject_employee_number,
        from {{ ref("int_surveys__survey_responses") }} as fr
        left join
            {{ ref("stg_people__renewal_approvers") }} as ra
            on fr.respondent_email = ra.approver_email
            and fr.academic_year = ra.academic_year
        where fr.survey_title = 'Renewal Approval Tool Processing'
    ),

    submissions_counter as (
        /* need 1 row per response to calculate rns */
        select
            ri.*,

            ssr.formatted_name as subject_preferred_name,
            ssr.sam_account_name as subject_samaccountname,
            ssr.user_principal_name as subject_userprincipalname,

            row_number() over (
                partition by
                    ri.survey_id,
                    ri.campaign_academic_year,
                    ri.campaign_reporting_term,
                    ri.subject_employee_number,
                    ri.approval_level
                order by ri.date_submitted desc
            ) as rn_level_approval,

            row_number() over (
                partition by
                    ri.survey_id,
                    ri.campaign_academic_year,
                    ri.campaign_reporting_term,
                    ri.subject_employee_number
                order by ri.date_submitted desc
            ) as rn_approval,
        from response_identifiers as ri
        inner join
            {{ ref("int_people__staff_roster") }} as ssr
            on ri.subject_employee_number = ssr.employee_number
        where ri.question_title = 'Employee Name'
    ),

    pre_pivot as (
        select survey_response_id, question_shortname, answer,
        from response_identifiers
        where question_title != 'Employee Name'
    ),

    pivoted_responses as (
        select
            survey_response_id,

            /* pivot cols */
            add_comp_amt_1,
            add_comp_amt_2,
            add_comp_amt_3,
            add_comp_amt_4,
            add_comp_amt_5,
            add_comp_name_1,
            add_comp_name_2,
            add_comp_name_3,
            add_comp_name_4,
            add_comp_name_5,
            dept_and_job,
            final_confirmation,
            next_year_seat,
            renewal_decision,
            salary_confirmation,
            salary_modification_explanation,
            salary_rule,
            salary,
        from
            pre_pivot pivot (
                max(answer) for question_shortname in (
                    'add_comp_amt_1',
                    'add_comp_amt_2',
                    'add_comp_amt_3',
                    'add_comp_amt_4',
                    'add_comp_amt_5',
                    'add_comp_name_1',
                    'add_comp_name_2',
                    'add_comp_name_3',
                    'add_comp_name_4',
                    'add_comp_name_5',
                    'dept_and_job',
                    'final_confirmation',
                    'next_year_seat',
                    'renewal_decision',
                    'salary_confirmation',
                    'salary_modification_explanation',
                    'salary_rule',
                    'salary'
                )
            )

    ),

    clean_responses as (

        select
            sc.survey_id,
            sc.survey_title,
            sc.survey_response_id,
            sc.respondent_email,
            sc.campaign_academic_year,
            sc.campaign_name,
            sc.campaign_reporting_term,
            sc.respondent_employee_number,
            sc.subject_employee_number,
            sc.approval_level,
            sc.date_started,
            sc.date_submitted,
            sc.rn_level_approval,
            sc.rn_approval,
            sc.respondent_preferred_name,
            sc.respondent_samaccountname,
            sc.respondent_userprincipalname,
            sc.subject_preferred_name,
            sc.subject_samaccountname,
            sc.subject_userprincipalname,

            pr.dept_and_job,
            pr.final_confirmation,
            pr.next_year_seat,
            pr.renewal_decision,
            pr.salary,
            pr.salary_confirmation,
            pr.salary_modification_explanation,
            pr.salary_rule,
            pr.add_comp_amt_1,
            pr.add_comp_amt_2,
            pr.add_comp_amt_3,
            pr.add_comp_amt_4,
            pr.add_comp_amt_5,
            pr.add_comp_name_1,
            pr.add_comp_name_2,
            pr.add_comp_name_3,
            pr.add_comp_name_4,
            pr.add_comp_name_5,

            concat(
                coalesce(
                    concat(pr.add_comp_name_1, ': $', pr.add_comp_amt_1, '; '), ''
                ),
                coalesce(
                    concat(pr.add_comp_name_2, ': $', pr.add_comp_amt_2, '; '), ''
                ),
                coalesce(
                    concat(pr.add_comp_name_3, ': $', pr.add_comp_amt_3, '; '), ''
                ),
                coalesce(
                    concat(pr.add_comp_name_4, ': $', pr.add_comp_amt_4, '; '), ''
                ),
                coalesce(concat(pr.add_comp_name_5, ': $', pr.add_comp_amt_5, '; '), '')
            ) as concated_add_comp,
        from submissions_counter as sc
        inner join
            pivoted_responses as pr on sc.survey_response_id = pr.survey_response_id
    )

select
    *,
    case
        when rn_approval = 1
        then 'Valid Approval'
        when
            lag(renewal_decision) over (
                partition by campaign_academic_year, subject_employee_number
                order by rn_approval
            )
            != renewal_decision
        then 'Overriden Approval - Renewal Decision'
        when
            lag(dept_and_job) over (
                partition by campaign_academic_year, subject_employee_number
                order by rn_approval
            )
            != dept_and_job
        then 'Overriden Approval - Job/Dept'
        when
            lag(salary) over (
                partition by campaign_academic_year, subject_employee_number
                order by rn_approval
            )
            != salary
        then 'Overriden Approval - Salary'
        when
            lag(concated_add_comp) over (
                partition by campaign_academic_year, subject_employee_number
                order by rn_approval
            )
            != concated_add_comp
        then 'Overriden Approval - Additional Compensation'
        else 'Valid Approval'
    end as valid_approval,

from clean_responses
