/* Student Number from Family Google Forms Survey*/
with
    family_responses_google as (
        select
            fr1.response_id,
            (
                select text_value
                from {{ ref("base_google_forms__form_responses") }} as fr2
                where
                    fr2.response_id = fr1.response_id
                    and fr2.item_abbreviation = 'family_respondent_number'
            ) as respondent_number
        from {{ ref("base_google_forms__form_responses") }} as fr1
        group by fr1.response_id
    ),
    /* Student Number from Family Alchemer Survey*/
    family_responses_alchemer as (
        select
            sr1.survey_id,
            sr1.response_id,
            (
                select response_value
                from {{ ref("base_alchemer__survey_results") }} as sr2
                where
                    sr2.response_id = sr1.response_id
                    and sr2.survey_id = sr1.survey_id
                    and sr2.question_short_name = 'student_number'
                    and response_value is not null
            ) as respondent_number
        from {{ ref("base_alchemer__survey_results") }} as sr1
        where survey_id = 6829997
        group by sr1.survey_id, sr1.response_id

    )

/* School Community Diagnostics from Google Forms*/
select
    fr.form_id as survey_id,
    fr.info_title as survey_title,
    fr.response_id as survey_response_id,
    fr.item_title as question_title,
    fr.item_abbreviation as question_shortname,
    fr.text_value as answer,
    fr.text_value as answer_value,
    timestamp(fr.last_submitted_time) as date_submitted,
    srh.employee_number as staff_respondent_number,
    se.student_number as student_respondent_number,
    safe_cast(frg.respondent_number as int64) as family_respondent_number,
    case
        when fr.info_title like '%Staff%'
        then 'Staff'
        when fr.info_title like '%Student%'
        then 'Student'
        when fr.info_title like '%Family%'
        then 'Family'
    end as survey_audience,
    {{
        teamster_utils.date_to_fiscal_year(
            date_field="timestamp(fr.last_submitted_time)",
            start_month=7,
            year_source="start",
        )
    }} as academic_year,

from {{ ref("base_google_forms__form_responses") }} as fr
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on fr.respondent_email = srh.google_email
    and timestamp(fr.last_submitted_time)
    between srh.work_assignment_start_date and srh.work_assignment_end_date
left join
    {{ ref("base_powerschool__student_enrollments") }} as se
    on fr.respondent_email = se.student_email_google
left join family_responses_google as frg on frg.response_id = frg.respondent_number
where fr.item_abbreviation like '%scd%'

union all


/* School Community Diagnostics from Alchemer*/
select
    safe_cast(sr.survey_id as string) as survey_id,
    sr.survey_title,
    safe_cast(sr.response_id as string) as survey_response_id,
    regexp_replace(sr.question_title_english, '<[^>]+>', '') as question_title,
    sr.question_short_name as question_shortname,
    sr.response_value as answer,
    sr.response_value as answer_value,
    sr.response_date_submitted as date_submitted,
    ri.respondent_employee_number as staff_respondent_number,
    null as student_respondent_number,
    safe_cast(fra.respondent_number as int64) as family_respondent_number,
    case
        when sr.survey_title like '%Engagement%'
        then 'Staff'
        when sr.survey_title like '%Family%'
        then 'Family'
    end as survey_audience,
    {{
        teamster_utils.date_to_fiscal_year(
            date_field="sr.response_date_submitted",
            start_month=7,
            year_source="start",
        )
    }} as academic_year,

from {{ ref("base_alchemer__survey_results") }} as sr
left join
    {{ ref("int_surveys__response_identifiers") }} as ri
    on sr.survey_id = ri.survey_id
    and sr.response_id = ri.response_id
left join
    family_responses_alchemer fra
    on sr.survey_id = fra.survey_id
    and sr.response_id = fra.response_id
where sr.question_short_name like '%scd%'
