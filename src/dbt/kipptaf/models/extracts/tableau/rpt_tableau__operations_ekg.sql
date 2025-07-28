with roster as (
    select formatted_name as respondent, google_email, job_title as respondent_job_title, home_work_location_name as respondent_location,
    from {{ ref("int_people__staff_roster") }} 
),

schools as (
    select * from {{ ref('stg_people__campus_crosswalk') }}
),

form_responses as (
    select 
    form_id,
    info_document_title as survey_title,
    item_id,
    item_title as section_title,
    question_id,
    question_title,
    item_abbreviation,
    response_id,
    last_submitted_date_local,
    respondent_email,
    text_value, 
    if(regexp_contains(text_value, r'^-?\d+$'),safe_cast(text_value as int), null) as text_value_int,
    from {{ ref("int_google_forms__form_responses") }} 
    -- filtering for Operations EKG Form
    where form_id = '1J4ce4NUNVZq5ia7HCPUfhuiWjqILik2mBu-FVaRwxFM'
    and text_value is not null
),

responses_pivoted as (
    select *, 
    -- pivoting out walkthrough round and school selection items 
    max(case when item_id = '27596233' then text_value end) over (
        partition by response_id
    ) as walkthrough_round,
    max(case when item_id = '669334db' then text_value end) over (
        partition by response_id
    ) as school, 
    from form_responses
),

final as (
    select 
    roster.*,
    responses_pivoted.*,
    schools.region,
    schools.grade_band, 
    from responses_pivoted
    left join roster on responses_pivoted.respondent_email = roster.google_email
    left join schools on responses_pivoted.school = schools.Location_Name
    where item_id not in ('27596233','669334db')
)

select * from final 
