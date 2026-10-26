with
    enriched as (
        select
            fr.form_id as survey_id,
            fr.response_id as survey_response_id,
            fr.question_id as survey_question_id,
            fr.item_title as question_title,
            fr.item_abbreviation as question_shortname,
            fr.item_abbreviation_lower as question_shortname_lower,
            fr.answer,
            fr.answer_value,
            fr.is_open_ended,

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
        from {{ ref("int_google_forms__form_responses") }} as fr
        inner join
            {{ ref("int_surveys__survey_submissions") }} as ss
            on fr.form_id = ss.survey_id
            and fr.response_id = ss.survey_response_id

        union all

        select
            survey_id,
            survey_response_id,
            survey_question_id,
            question_title,
            question_shortname,
            question_shortname_lower,
            answer,
            answer_value,
            is_open_ended,
            survey_title,
            respondent_email,
            academic_year,
            term_code,
            term_name,
            respondent_employee_number,
            respondent_preferred_name,
            respondent_samaccountname,
            respondent_userprincipalname,
            date_started,
            date_submitted,
            survey_response_link,
            round_rn,
            respondent_identifier,
            survey_submission_key,
        from {{ ref("int_surveys__alchemer_responses") }}
    ),

    /* the crosswalk is already one row per abbreviation, so this joins at
       grain with no projection. Its unique_lowered_abbreviation test is what
       keeps lowering from collapsing two rows into a fan-out. */
    question_departments as (
        select abbreviation, rated_department_code, rated_department_name,
        from {{ ref("stg_google_sheets__google_forms__question_department_crosswalk") }}
        where abbreviation is not null
    )

select
    e.survey_id,
    e.survey_response_id,
    e.survey_question_id,
    e.question_title,
    e.question_shortname,
    e.answer,
    e.answer_value,
    e.is_open_ended,
    e.survey_title,
    e.respondent_email,
    e.academic_year,
    e.term_code,
    e.term_name,
    e.respondent_employee_number,
    e.respondent_preferred_name,
    e.respondent_samaccountname,
    e.respondent_userprincipalname,
    e.date_started,
    e.date_submitted,
    e.survey_response_link,
    e.round_rn,
    e.respondent_identifier,
    e.survey_submission_key,

    qd.rated_department_code,
    qd.rated_department_name,
from enriched as e
left join question_departments as qd on e.question_shortname_lower = qd.abbreviation
