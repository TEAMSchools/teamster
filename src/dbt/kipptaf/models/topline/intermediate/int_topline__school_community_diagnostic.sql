select
    sr.academic_year,

    se.student_number,
    se.schoolid,

    round(avg(ac.response_int), 1) as average_rating,
from {{ ref("int_surveys__survey_responses") }} as sr
inner join
    {{ ref("int_extracts__student_enrollments") }} as se
    on sr.respondent_email = se.student_email
    and sr.academic_year = se.academic_year
    and se.is_enrolled_y1
left join
    {{ ref("stg_google_sheets__surveys__scd_answer_crosswalk") }} as ac
    on sr.question_shortname = ac.question_code
    and sr.answer = ac.response
where
    sr.survey_title = 'School Community Diagnostic Student Survey'
    and sr.question_shortname like '%scd%'
    and sr.term_code = 'SCD'
    and sr.academic_year >= {{ var("current_academic_year") - 1 }}
group by sr.academic_year, se.student_number, se.schoolid
