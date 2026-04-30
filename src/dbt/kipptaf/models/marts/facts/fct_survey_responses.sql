with
    /* Staff/student survey responses from int_surveys__survey_responses
       (already deduped upstream on survey_id, survey_response_id,
       respondent_identifier, question_shortname). */
    general_responses as (
        select
            sr.survey_id,
            sr.survey_response_id,
            sr.question_shortname,
            sr.respondent_identifier,
            sr.answer as response_text,

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

            cast(ms.respondent_df_employee_number as string) as respondent_identifier,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        where ms.campaign_academic_year is not null
    ),

    all_responses as (
        select
            survey_id,
            survey_response_id,
            question_shortname,
            respondent_identifier,
            response_text,
            response_value,
        from general_responses
        union all
        select
            survey_id,
            survey_response_id,
            question_shortname,
            respondent_identifier,
            response_text,
            response_value,
        from manager_responses
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
from all_responses
