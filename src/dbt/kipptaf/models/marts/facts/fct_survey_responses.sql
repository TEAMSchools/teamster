with
    /* Staff/student survey responses. PK hashes survey_question_id rather
       than question_shortname because Alchemer surveys can reuse a
       question_shortname across multiple internal question_ids. */
    general_responses as (
        select
            sr.survey_id,
            sr.survey_response_id,
            sr.survey_question_id,
            sr.question_shortname,
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
            ms.survey_question_id,
            ms.question_shortname,
            ms.answer as response_text,
            ms.answer_value as response_value,

            ms.effective_survey_response_id as survey_response_id,
        from {{ ref("int_surveys__manager_survey_details") }} as ms
        where ms.campaign_academic_year is not null
    ),

    all_responses as (
        select
            survey_id,
            survey_response_id,
            survey_question_id,
            question_shortname,
            response_text,
            response_value,
        from general_responses
        union all
        select
            survey_id,
            survey_response_id,
            survey_question_id,
            question_shortname,
            response_text,
            response_value,
        from manager_responses
    )

/*
 * survey_submission_key comes from int_surveys__survey_submissions rather than
 * being re-hashed here, so the composition lives in exactly one place. The join
 * to fct_survey_submissions stays: it is the filter that keeps this fact to the
 * submissions the fact actually models.
 */
select
    ar.response_value,
    ar.response_text,

    ss.survey_submission_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["ar.survey_id", "ar.survey_response_id", "ar.survey_question_id"]
        )
    }} as survey_response_key,

    {{ dbt_utils.generate_surrogate_key(["ar.question_shortname"]) }}
    as survey_question_key,
from all_responses as ar
inner join
    {{ ref("int_surveys__survey_submissions") }} as ss
    on ar.survey_id = ss.survey_id
    and ar.survey_response_id = ss.survey_response_id
inner join
    {{ ref("fct_survey_submissions") }} as fss
    on ss.survey_submission_key = fss.survey_submission_key
