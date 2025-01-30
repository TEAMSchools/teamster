with
    response_identifiers as (
        select
            fr.form_id as survey_id,
            fr.info_title as survey_title,
            fr.response_id as survey_response_id,
            fr.respondent_email,
            fr.create_timestamp as date_started,
            fr.last_submitted_timestamp as date_submitted,

            up.employee_number as respondent_df_employee_number,

            rt.academic_year as campaign_academic_year,
            rt.name as campaign_name,
            rt.code as campaign_reporting_term,

            ra.approval_level

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
            {{ ref("stg_people__renewal_approvers")}} as ra
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
            respondent_df_employee_number,
            subject_df_employee_number,
            approval_level
            date_started,
            date_submitted,

            row_number() over (
                partition by
                    survey_id,
                    survey_response_id,
                    campaign_academic_year,
                    campaign_reporting_term,
                    respondent_df_employee_number,
                    subject_df_employee_number,
                    approval_level
            ) as rn_level_approval,
            row_number() over (
                partition by
                    survey_id,
                    survey_response_id,
                    campaign_academic_year,
                    campaign_reporting_term,
                    respondent_df_employee_number,
                    subject_df_employee_number
            ) as rn_approval,
        from response_identifiers
)

select * from submissions_counter