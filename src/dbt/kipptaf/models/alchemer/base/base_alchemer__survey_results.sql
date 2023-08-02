select
    s.id as survey_id,
    s.title as survey_title,

    sr.id as response_id,
    sr.status as response_status,
    sr.contact_id as response_contact_id,
    sr.date_started as response_date_started,
    sr.date_submitted as response_date_submitted,
    sr.response_time,

    sq.id as question_id,
    sq.shortname as question_short_name,
    sq.title_english as question_title_english,
    sq.type as question_type,
    if(
        sq.shortname in unnest({{ var("alchemer_survey_identifier_short_names") }}),
        true,
        false
    ) as is_identifier_question,

    srd.string_value as response_string_value,
    srd.map_value as response_map_value,
    srd.option_value as response_option_value,
    srd.rank_value as response_rank_value,

    sc.fiscal_year as campaign_fiscal_year,
    sc.name as campaign_name,
    sc.link_close_date as campaign_link_close_date,
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
