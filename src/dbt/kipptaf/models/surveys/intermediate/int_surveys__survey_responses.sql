with
    alchemer_results as (
        select
            question_title_english,
            question_short_name,
            response_value,

            cast(survey_id as string) as survey_id,
            cast(response_id as string) as survey_response_id,
            cast(question_id as string) as survey_question_id,
        from {{ source("alchemer", "base_alchemer__survey_results") }}
    ),

    enriched as (
        select
            fr.form_id as survey_id,
            fr.response_id as survey_response_id,
            fr.question_id as survey_question_id,
            fr.item_title as question_title,
            fr.item_abbreviation as question_shortname,

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

            safe_cast(fr.text_value as numeric) as answer_value,

            -- answer sits after answer_value in both branches so the union
            -- binds by position
            coalesce(fr.text_value, fr.file_upload_file_name) as answer,

            if(safe_cast(fr.text_value as int) is null, 1, 0) as is_open_ended,
        from {{ ref("int_google_forms__form_responses") }} as fr
        inner join
            {{ ref("int_surveys__survey_submissions") }} as ss
            on fr.form_id = ss.survey_id
            and fr.response_id = ss.survey_response_id

        union all

        select
            sr.survey_id,
            sr.survey_response_id,
            sr.survey_question_id,

            sr.question_title_english as question_title,
            sr.question_short_name as question_shortname,

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

            safe_cast(sr.response_value as numeric) as answer_value,

            sr.response_value as answer,

            if(safe_cast(sr.response_value as int) is null, 1, 0) as is_open_ended,
        from alchemer_results as sr
        inner join
            {{ ref("int_surveys__survey_submissions") }} as ss
            on sr.survey_id = ss.survey_id
            and sr.survey_response_id = ss.survey_response_id
    ),

    question_departments as (
        /* the crosswalk is already one row per abbreviation, so this joins at
           grain with no projection. Lowered on both sides because sheet entry is
           not case-constrained; the crosswalk's unique_lowered_abbreviation test
           is what keeps lowering from collapsing two rows into a fan-out. */
        select
            rated_department_code,
            rated_department_name,

            lower(abbreviation) as question_shortname,
        from {{ ref("stg_google_sheets__google_forms__question_department_crosswalk") }}
        where abbreviation is not null
    )

select e.*, qd.rated_department_code, qd.rated_department_name,
from enriched as e
left join
    question_departments as qd on lower(e.question_shortname) = qd.question_shortname
