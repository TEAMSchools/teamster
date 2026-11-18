with
    windowed_surveys as (
        -- grain projection, not dup-masking
        select distinct `name`,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where type = 'SURVEY'
    )

select s.survey_id, s.survey_response_id, s.survey_title, s.date_submitted,
from {{ ref("int_surveys__survey_submissions") }} as s
inner join windowed_surveys as ws on s.survey_title = ws.`name`
where s.academic_year is null or s.term_code is null
