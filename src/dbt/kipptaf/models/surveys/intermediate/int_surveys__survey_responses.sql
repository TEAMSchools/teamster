select
    fr.form_id as survey_id,
    fr.info_title as survey_title,
    fr.response_id as survey_response_id,
    fr.text_value as answer,
    fr.item_title as question_title,
    fr.item_abbreviation as question_shortname,
    fr.rn_form_item_respondent_submitted_desc as rn,
    fr.respondent_email,

    rt.code as survey_code,
    rt.type as survey_type,
    rt.academic_year,

    safe_cast(fr.text_value as numeric) as answer_value,
    timestamp(fr.create_time) as date_started,
    timestamp(fr.last_submitted_time) as date_submitted,

    concat(
        'https://docs.google.com/forms/d/',
        fr.form_id,
        '/edit#response=',
        fr.response_id
    ) as survey_response_link,

    if(safe_cast(fr.text_value as int) is null, 1, 0) as is_open_ended,
from {{ ref("base_google_forms__form_responses") }} as fr
left join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = fr.info_title
    and date(fr.last_submitted_time) between rt.start_date and rt.end_date

union all

select
    safe_cast(sr.survey_id as string) as survey_id,
    sr.survey_title,
    safe_cast(sr.response_id as string) as survey_response_id,
    sr.response_value as answer,
    sr.question_title_english as question_title,
    sr.question_short_name as question_shortname,
    1 as rn,
    ri.respondent_mail as respondent_email,

    coalesce(regexp_extract(sr.campaign_name, r'\s(.*)'), rt.code) as survey_code,
    'SURVEY' as survey_type,
    coalesce(sr.campaign_fiscal_year - 1, rt.academic_year) as academic_year,

    safe_cast(sr.response_value as numeric) as answer_value,

    sr.response_date_started as date_started,
    sr.response_date_submitted as date_submitted,

    concat(
        sr.survey_link_default, '?snc=', sr.response_session_id, '&sg_navigate=start'
    ) as survey_response_link,

    if(safe_cast(sr.response_value as int) is null, 1, 0) as is_open_ended,
from
    /* hardcode disabled model */
    kipptaf_alchemer.base_alchemer__survey_results as sr
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = sr.survey_title
    and sr.response_date_submitted_date between rt.start_date and rt.end_date
left join
    /* hardcode disabled model */
    kipptaf_surveys.int_surveys__response_identifiers as ri
    on sr.survey_id = ri.survey_id
    and sr.response_id = ri.response_id
