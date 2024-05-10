/* School Community Diagnostics from Google Forms*/
select
    fr.form_id as survey_id,
    fr.info_title as survey_title,
    fr.response_id as survey_response_id,
    fr.text_value as answer,
    fr.item_title as question_title,
    fr.item_abbreviation as question_shortname,
    fr.rn_form_item_respondent_submitted_desc as rn,

    rt.code as survey_code,
    rt.type as survey_type,
    rt.academic_year,

    fr.text_value as answer_value,
    timestamp(fr.last_submitted_time) as date_submitted,

    case
        when fr.info_title like '%Staff%'
        then 'Staff'
        when fr.info_title like '%Student%'
        then 'Student'
        when fr.info_title like '%Family%'
        then 'Family'
    end as survey_audience,
from {{ ref("base_google_forms__form_responses") }} as fr
left join
    {{ ref("stg_reporting__terms") }} as rt
    on fr.info_title like concat('%', rt.name, '%')
    and date(fr.last_submitted_time) between rt.start_date and rt.end_date
where fr.item_abbreviation like '%scd%'

union all

/* School Community Diagnostics from Alchemer*/
select
    safe_cast(sr.survey_id as string) as survey_id,
    sr.survey_title,
    safe_cast(sr.response_id as string) as survey_response_id,
    sr.response_value as answer,
    sr.question_title_english as question_title,
    sr.question_short_name as question_shortname,
    1 as rn,

    regexp_extract(sr.campaign_name, r'\s(.*)') as survey_code,
    'SURVEY' as survey_type,
    sr.campaign_fiscal_year - 1 as academic_year,

    sr.response_value as answer_value,

    sr.response_date_submitted as date_submitted,

    case
        when sr.survey_title like '%Engagement%'
        then 'Staff'
        when sr.survey_title like '%Family%'
        then 'Family'
    end as survey_audience,
from {{ ref("base_alchemer__survey_results") }} as sr
left join
    {{ ref("stg_reporting__terms") }} as rt
    on rt.name = sr.survey_title
    and sr.response_date_submitted_date between rt.start_date and rt.end_date
inner join
    {{ ref("int_surveys__response_identifiers") }} as ri
    on sr.survey_id = ri.survey_id
    and sr.response_id = ri.response_id
where sr.question_short_name like '%scd%'
