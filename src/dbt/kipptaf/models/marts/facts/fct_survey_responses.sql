with
    /* Staff/student survey responses from int_surveys__survey_responses */
    general_responses as (
        select
            sr.survey_id,
            sr.survey_response_id,
            sr.question_shortname,
            sr.answer as response_text,
            sr.respondent_employee_number,
            sr.respondent_email,
            sr.academic_year,
            sr.survey_title,

            safe_cast(sr.answer as numeric) as response_value,
        from {{ ref("int_surveys__survey_responses") }} as sr
        where
            sr.survey_title in (
                'School Community Diagnostic Staff Survey',
                'School Community Diagnostic Student Survey',
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic',
                'Engagement & Support Surveys'
            )
            and sr.question_shortname is not null
    ),

    /* Manager Survey responses */
    manager_responses as (
        select
            ms.survey_id,
            ms.question_shortname,
            ms.answer as response_text,
            ms.answer_value as response_value,
            ms.respondent_df_employee_number as respondent_employee_number,
            ms.campaign_academic_year as academic_year,

            coalesce(
                ms.survey_response_id,
                concat(
                    ms.respondent_df_employee_number,
                    '_',
                    ms.subject_df_employee_number,
                    '_',
                    ms.campaign_reporting_term
                )
            ) as survey_response_id,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        where ms.campaign_academic_year is not null
    ),

    /* Build submission keys to join to fct_survey_submissions */
    general_with_keys as (
        select
            gr.survey_id,
            gr.survey_response_id,
            gr.question_shortname,
            gr.response_text,
            gr.response_value,

            case
                when gr.survey_title like '%Staff%'
                then 'staff'
                when gr.survey_title like '%Student%'
                then 'student'
                when gr.survey_title like '%Family%'
                then 'family'
                when gr.survey_title like '%Engagement%'
                then 'staff'
                when gr.survey_title like '%Re-Commitment%'
                then 'family'
                else 'staff'
            end as respondent_population,

            coalesce(
                cast(gr.respondent_employee_number as string), gr.respondent_email
            ) as respondent_identifier,
        from general_responses as gr
    ),

    manager_with_keys as (
        select
            mr.survey_id,
            mr.survey_response_id,
            mr.question_shortname,
            mr.response_text,
            mr.response_value,

            'staff' as respondent_population,

            cast(mr.respondent_employee_number as string) as respondent_identifier,
        from manager_responses as mr
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    all_responses as (
        select *,
        from general_with_keys
        union all
        select *,
        from manager_with_keys
    ),

    deduped as (
        {{
            dbt_utils.deduplicate(
                relation="all_responses",
                partition_by="survey_id, survey_response_id, respondent_identifier, question_shortname",
                order_by="response_text asc",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_id",
                "survey_response_id",
                "respondent_identifier",
                "question_shortname",
            ]
        )
    }} as survey_response_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "survey_id",
                "survey_response_id",
                "respondent_identifier",
            ]
        )
    }} as survey_submission_key,

    {{ dbt_utils.generate_surrogate_key(["question_shortname"]) }}
    as survey_question_key,

    response_value,
    response_text,
from deduped
