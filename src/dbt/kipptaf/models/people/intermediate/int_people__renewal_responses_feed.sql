with
    response_identifiers as (
        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,
            fr.respondent_email,
            fr.create_timestamp as date_started,
            fr.last_submitted_timestamp as date_submitted,

            up.employee_number as respondent_employee_number,

            rt.academic_year as campaign_academic_year,
            rt.name as campaign_name,
            rt.code as campaign_reporting_term,

            ra.approval_level,

            safe_cast(
                regexp_extract(fr.text_value, r'\((\d{6})\)') as integer
            ) as subject_employee_number,
        from {{ ref("base_google_forms__form_responses") }} as fr
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on fr.respondent_email = up.google_email
        left join
            {{ ref("stg_reporting__terms") }} as rt
            on fr.last_submitted_date_local between rt.start_date and rt.end_date
            and rt.type = 'RENEW'
            and rt.code = 'RENEW'
        left join
            {{ ref("stg_people__renewal_approvers") }} as ra
            on fr.respondent_email = ra.approver_email
            and rt.academic_year = ra.academic_year
        where
            fr.form_id = '1QfYO4OCK3vLxAL_Xx9jIoDVnb29l-lRb1tP8PmKU2iU'
            and fr.question_id = '4d8bc5d5'
    ),

    submissions_counter as (
        select
            survey_id,
            survey_title,
            survey_response_id,
            respondent_email,
            campaign_academic_year,
            campaign_name,
            campaign_reporting_term,
            respondent_employee_number,
            subject_employee_number,
            approval_level,
            date_started,
            date_submitted,

            row_number() over (
                partition by
                    survey_id,
                    campaign_academic_year,
                    campaign_reporting_term,
                    subject_employee_number,
                    approval_level
                order by date_submitted desc
            ) as rn_level_approval,
            row_number() over (
                partition by
                    survey_id,
                    campaign_academic_year,
                    campaign_reporting_term,
                    subject_employee_number
                order by date_submitted desc
            ) as rn_approval,
        from response_identifiers
    ),

    pivoted_responses as (
        select
            response_id as survey_response_id,
            max(
                case when item_abbreviation = 'dept_and_job' then text_value end
            ) as dept_and_job,
            max(
                case when item_abbreviation = 'final_confirmation' then text_value end
            ) as final_confirmation,
            max(
                case when item_abbreviation = 'next_year_seat' then text_value end
            ) as next_year_seat,
            max(
                case when item_abbreviation = 'renewal_decision' then text_value end
            ) as renewal_decision,
            max(case when item_abbreviation = 'salary' then text_value end) as salary,
            max(
                case when item_abbreviation = 'salary_confirmation' then text_value end
            ) as salary_confirmation,
            max(
                case
                    when item_abbreviation = 'salary_modification_explanation'
                    then text_value
                end
            ) as salary_modification_explanation,
            max(
                case when item_abbreviation = 'salary_rule' then text_value end
            ) as salary_rule,
            max(
                case when item_abbreviation = 'add_comp_amt_1' then text_value end
            ) as add_comp_amt_1,
            max(
                case when item_abbreviation = 'add_comp_amt_2' then text_value end
            ) as add_comp_amt_2,
            max(
                case when item_abbreviation = 'add_comp_amt_3' then text_value end
            ) as add_comp_amt_3,
            max(
                case when item_abbreviation = 'add_comp_amt_4' then text_value end
            ) as add_comp_amt_4,
            max(
                case when item_abbreviation = 'add_comp_amt_5' then text_value end
            ) as add_comp_amt_5,
            max(
                case when item_abbreviation = 'add_comp_name_1' then text_value end
            ) as add_comp_name_1,
            max(
                case when item_abbreviation = 'add_comp_name_2' then text_value end
            ) as add_comp_name_2,
            max(
                case when item_abbreviation = 'add_comp_name_3' then text_value end
            ) as add_comp_name_3,
            max(
                case when item_abbreviation = 'add_comp_name_4' then text_value end
            ) as add_comp_name_4,
            max(
                case when item_abbreviation = 'add_comp_name_5' then text_value end
            ) as add_comp_name_5,

        from {{ ref("base_google_forms__form_responses") }}
        where
            form_id = '1QfYO4OCK3vLxAL_Xx9jIoDVnb29l-lRb1tP8PmKU2iU'
            and question_id != '4d8bc5d5'
        group by response_id
    )

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

    ssr.preferred_name_lastfirst as subject_preferred_name,
    ssr.sam_account_name as subject_samaccountname,
    ssr.user_principal_name as subject_userprincipalname,

    rsr.preferred_name_lastfirst as respondent_preferred_name,
    rsr.sam_account_name as respondent_samaccountname,
    rsr.user_principal_name as respondent_userprincipalname,

    concat(
        coalesce(concat(add_comp_name_1, ': $', add_comp_amt_1, '; '), ''),
        coalesce(concat(add_comp_name_2, ': $', add_comp_amt_2, '; '), ''),
        coalesce(concat(add_comp_name_3, ': $', add_comp_amt_3, '; '), ''),
        coalesce(concat(add_comp_name_4, ': $', add_comp_amt_4, '; '), ''),
        coalesce(concat(add_comp_name_5, ': $', add_comp_amt_5, '; '), '')
    ) as concated_add_comp

from submissions_counter as sc
inner join pivoted_responses as pr on sc.survey_response_id = pr.survey_response_id
inner join
    {{ ref("base_people__staff_roster") }} as ssr
    on ssr.employee_number = sc.subject_employee_number
inner join
    {{ ref("base_people__staff_roster") }} as rsr
    on rsr.employee_number = sc.respondent_employee_number
