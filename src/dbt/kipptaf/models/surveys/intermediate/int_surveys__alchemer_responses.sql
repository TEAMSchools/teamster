with
    alchemer_results as (
        select
            question_title_english,
            question_short_name,
            response_value,

            cast(survey_id as string) as survey_id,
            cast(response_id as string) as survey_response_id,
            cast(question_id as string) as survey_question_id,

            lower(question_short_name) as question_shortname_lower,

            safe_cast(response_value as numeric) as answer_value,

            if(safe_cast(response_value as int) is null, 1, 0) as is_open_ended,
        from {{ source("alchemer", "base_alchemer__survey_results") }}
    )

select
    sr.survey_id,
    sr.survey_response_id,
    sr.survey_question_id,
    sr.question_shortname_lower,
    sr.answer_value,
    sr.is_open_ended,

    sr.question_title_english as question_title,
    sr.question_short_name as question_shortname,
    sr.response_value as answer,

    ss.survey_title,
    ss.respondent_email,
    ss.academic_year,
    ss.term_code,
    ss.term_name,
    ss.respondent_employee_number,
    ss.respondent_preferred_name,
    ss.respondent_samaccountname,
    ss.respondent_userprincipalname,
    ss.date_started,
    ss.date_submitted,
    ss.survey_response_link,
    ss.round_rn,
    ss.respondent_identifier,
    ss.survey_submission_key,
from alchemer_results as sr
inner join
    {{ ref("int_surveys__alchemer_submissions") }} as ss
    on sr.survey_id = ss.survey_id
    and sr.survey_response_id = ss.survey_response_id
