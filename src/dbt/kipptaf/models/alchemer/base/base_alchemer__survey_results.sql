select
    s.id as survey_id,
    s.title as survey_title,
    s.link_default as survey_link_default,

    sr.id as response_id,
    sr.session_id as response_session_id,
    sr.contact_id as response_contact_id,
    sr.status as response_status,
    sr.date_started as response_date_started,
    sr.date_submitted as response_date_submitted,
    sr.response_time,

    sq.id as question_id,
    sq.shortname as question_short_name,
    sq.title_english as question_title_english,
    sq.type as question_type,

    srd.string_value as response_string_value,
    srd.option_value as response_option_value,
    srd.rank_value as response_rank_value,

    sc.fiscal_year as campaign_fiscal_year,
    sc.name as campaign_name,
    sc.link_close_date as campaign_link_close_date,

    date(sr.date_started) as response_date_started_date,
    date(sr.date_submitted) as response_date_submitted_date,

    coalesce(srd.string_value, srd.option_value, srd.rank_value) as response_value,

    if(
        sq.shortname in (
            'respondent_employee_number',
            'respondent_df_employee_number',
            'respondent_userprincipalname',
            'respondent_adp_associate_id',
            'subject_df_employee_number',
            'employee_number',
            'email',
            'employee_preferred_name',
            'salesforce_id',
            'is_manager'
        ),
        true,
        false
    ) as is_identifier_question,
from {{ ref("stg_alchemer__survey") }} as s
inner join {{ ref("stg_alchemer__survey_response") }} as sr on s.id = sr.survey_id
inner join {{ ref("stg_alchemer__survey_question") }} as sq on s.id = sq.survey_id
left join
    {{ ref("stg_alchemer__survey_response__survey_data") }} as srd
    on sr.id = srd.survey_response_id
    and sr.survey_id = srd.survey_id
    and sq.id = srd.question_id
left join
    {{ ref("stg_alchemer__survey_campaign") }} as sc
    on sr.survey_id = sc.survey_id
    and sr.date_started between sc.link_open_date and sc.link_close_date
